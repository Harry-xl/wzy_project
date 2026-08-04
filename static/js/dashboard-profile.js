/**
 * StarPal — 能力画像模块
 * 实力环 / 趋势图 / 图表切换 / 薄弱预警 / AI 评语
 */
(function () {
  const DS = window.__DS;
  if (!DS) return;
  const { $, escapeHtml, userId } = DS;
  const dom = DS.dom;

  async function loadKnowledgePointsCached() {
    const now = Date.now();
    if (Array.isArray(DS.kpCache.items) && (now - DS.kpCache.ts) < DS.kpCache.ttl) return DS.kpCache.items;
    try {
      const resp = await apiClient.getKnowledgePoints();
      DS.kpCache.items = (resp?.success && Array.isArray(resp.items)) ? resp.items : [];
      DS.kpCache.ts = now;
      return DS.kpCache.items;
    } catch (_) { return []; }
  }

  function load() {
    const now = Date.now();
    if (DS.profileCache.data && (now - DS.profileCache.ts) < DS.profileCache.ttl) {
      const { profile, analysis, trendData } = DS.profileCache.data;
      renderAll(profile, analysis, trendData);
      return;
    }
    const sr = dom.strengthRing; if (sr) sr.innerHTML = '<div class="skeleton" style="width:140px;height:140px;border-radius:50%;margin:0 auto;"></div>';
    const st = dom.strengthTrend; if (st) st.innerHTML = '';
    const pca = dom.profileChartArea; if (pca) pca.innerHTML = '';
    const ppa = dom.profilePracticeArea; if (ppa) ppa.innerHTML = '';
    const paa = dom.profileAnalysisArea; if (paa) paa.innerHTML = '';

    apiClient.getUserProfile(userId).then(async resp => {
      if (!resp?.success) {
        const sr2 = dom.strengthRing; if (sr2) sr2.innerHTML = `<div class="empty-state"><div class="empty-state-title">${resp?.message || '获取失败'}</div></div>`;
        return;
      }
      const { profile, analysis } = resp;
      let trendData = null;
      try { const tr = await apiClient.getUserStrengthTrend(userId); if (tr?.success) trendData = tr.trend; } catch (_) { }
      DS.profileCache.data = { profile, analysis, trendData }; DS.profileCache.ts = Date.now();
      renderAll(profile, analysis, trendData);
    }).catch(() => {
      const sr3 = dom.strengthRing; if (sr3) sr3.innerHTML = '<div class="empty-state"><div class="empty-state-title">加载失败</div></div>';
    });
  }

  function renderAll(profile, analysis, trendData) {
    renderStrengthRing(profile);
    renderTrend(trendData);
    renderWeakAlerts(profile);   // ★ 薄弱知识点预警
    renderProfileChart(profile);
    renderPracticeGrid(profile);
    renderAiAnalysis(analysis);
  }

  // ========== 实力环 ==========
  function renderStrengthRing(profile) {
    const el = dom.strengthRing; if (!el) return;
    const s = (profile && typeof profile.user_strength === 'number') ? profile.user_strength : 0.5;
    const v = Math.max(0, Math.min(1, s));
    const pct = Math.round(v * 100);
    const { label, color } = DS.mapStrength(v);
    const circ = 2 * Math.PI * 56;
    const dash = circ * v;
    el.innerHTML = `
      <svg width="140" height="140" viewBox="0 0 140 140">
        <circle cx="70" cy="70" r="56" fill="none" stroke="var(--color-border)" stroke-width="10"/>
        <circle cx="70" cy="70" r="56" fill="none" stroke="${color}" stroke-width="10" stroke-dasharray="${dash} ${circ - dash}" stroke-linecap="round"/>
      </svg>
      <div class="strength-ring-value">
        <div class="strength-ring-num" style="color:${color}">${v.toFixed(2)}</div>
        <div class="strength-ring-label">${pct}% · ${label}</div>
      </div>`;
  }

  // ========== 实力趋势 ==========
  function renderTrend(trendData) {
    const el = dom.strengthTrend;
    if (!el || !Array.isArray(trendData) || trendData.length < 2) {
      if (el) el.innerHTML = '<p class="text-sm text-muted">多做几题后查看趋势</p>';
      return;
    }
    const w = 260, h = 64, pad = 8;
    const vals = trendData.map(d => d.value || 0);
    const maxV = Math.max(...vals), minV = Math.min(...vals), range = maxV - minV || 1;
    const points = trendData.map((d, i) => {
      const x = pad + (i / (trendData.length - 1)) * (w - 2 * pad);
      const y = pad + (1 - (d.value - minV) / range) * (h - 2 * pad);
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`;
    }).join(' ');
    // 渐变填充
    const areaPath = `M${pad},${h - pad} L${points.slice(1)} L${w - pad},${h - pad} Z`.replace(/^M(\S+)\s+L/, 'M$1 L');
    el.innerHTML = `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" style="background:var(--color-bg);border-radius:8px;">
      <path d="${areaPath}" fill="url(#trendGrad)" opacity="0.3"/>
      <defs><linearGradient id="trendGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#4F46E5"/><stop offset="100%" stop-color="#4F46E5" stop-opacity="0"/></linearGradient></defs>
      <path d="${points}" fill="none" stroke="#4F46E5" stroke-width="2" stroke-linecap="round"/>
    </svg>`;
  }

  // ========== ★ 薄弱知识点预警卡片 ==========
  function renderWeakAlerts(profile) {
    const area = $('#weakAlertArea');
    if (!area) return;
    const abilities = profile?.abilities || {};
    const weakEntries = Object.entries(abilities)
      .filter(([_, v]) => typeof v === 'number' && v < 0.4)
      .sort((a, b) => a[1] - b[1]);

    if (!weakEntries.length) {
      area.innerHTML = '<div class="card" style="text-align:center;padding:16px;margin-bottom:16px;"><span style="color:var(--color-success);">🎉 没有薄弱知识点，继续加油！</span></div>';
      return;
    }

    area.innerHTML = `
      <div class="card" style="margin-bottom:16px;border-left:4px solid var(--color-danger);">
        <h3 style="margin-bottom:8px;color:var(--color-danger);">⚠️ 薄弱知识点预警</h3>
        <p class="text-sm text-muted" style="margin-bottom:12px;">以下知识点熟练度较低，建议优先练习：</p>
        <div style="display:flex;flex-wrap:wrap;gap:8px;">
          ${weakEntries.map(([kp, lv]) => {
            const pct = Math.round(lv * 100);
            return `<div style="display:flex;align-items:center;gap:8px;padding:8px 12px;background:var(--color-danger-light);border-radius:8px;flex:1;min-width:180px;">
              <span style="font-size:13px;font-weight:500;flex:1;">${escapeHtml(kp)}</span>
              <span style="font-size:12px;color:#991B1B;font-weight:600;">${pct}%</span>
              <button class="btn btn-danger btn-sm" onclick="window.__DS.navigateTo('exam');setTimeout(()=>{const cbs=document.querySelectorAll('#kpFilterList input');if(cbs)cbs.forEach(c=>c.checked=c.value==='${escapeHtml(kp).replace(/'/g,"\\'")}');document.getElementById('examStartBtn')?.click()},400);">去练习</button>
            </div>`;
          }).join('')}
        </div>
      </div>`;
  }

  // ========== 图表 ==========
  function renderProfileChart(profile) {
    const area = dom.profileChartArea; if (!area) return;
    const abilities = profile?.abilities || {};
    const entries = Object.entries(abilities).filter(([_, v]) => typeof v === 'number');
    if (!entries.length) { area.innerHTML = ''; return; }
    entries.sort((a, b) => b[1] - a[1]);
    area.innerHTML = `
      <div class="chart-type-selector">
        <button class="chart-type-btn active" data-ctype="bar">条形图</button>
        <button class="chart-type-btn" data-ctype="radar">雷达图</button>
        <button class="chart-type-btn" data-ctype="donut">环形图</button>
      </div>
      <div id="chartRenderArea"></div>`;
    const renderArea = $('#chartRenderArea');
    renderBarChart(renderArea, entries);
    area.querySelector('.chart-type-selector').addEventListener('click', e => {
      const btn = e.target.closest('.chart-type-btn'); if (!btn) return;
      area.querySelectorAll('.chart-type-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      if (btn.dataset.ctype === 'bar') renderBarChart(renderArea, entries);
      else if (btn.dataset.ctype === 'radar') renderRadarChart(renderArea, entries);
      else renderDonutChart(renderArea, entries);
    });
  }

  function renderBarChart(container, entries) {
    const maxV = Math.max(...entries.map(([_, v]) => v));
    container.innerHTML = entries.map(([label, value]) => {
      const pct = maxV ? (value / maxV * 100) : 0;
      return `<div style="display:flex;align-items:center;gap:8px;margin:8px 0;">
        <span style="width:100px;font-size:12px;text-align:right;color:var(--color-text-secondary);">${escapeHtml(label)}</span>
        <div style="flex:1;height:18px;background:var(--color-border);border-radius:9px;overflow:hidden;">
          <div style="height:100%;background:var(--color-primary);width:${pct}%;border-radius:9px;transition:width .6s ease;"></div>
        </div>
        <span style="width:40px;font-size:12px;color:var(--color-text);">${value.toFixed(2)}</span>
      </div>`;
    }).join('');
  }

  function renderRadarChart(container, entries) {
    const n = entries.length;
    if (n < 3) { renderBarChart(container, entries); return; }
    const size = 260, cx = size / 2, cy = size / 2, r = 90;
    let svg = '';
    for (let lv = 1; lv <= 4; lv++) {
      const rr = r * lv / 4;
      const pts = entries.map((_, i) => {
        const a = -Math.PI / 2 + (2 * Math.PI * i) / n;
        return `${(cx + rr * Math.cos(a)).toFixed(1)},${(cy + rr * Math.sin(a)).toFixed(1)}`;
      }).join(' ');
      svg += `<polygon points="${pts}" fill="${lv % 2 ? '#fff' : '#f8fafc'}" stroke="#e2e8f0" stroke-width="0.5"/>`;
    }
    const dataPts = entries.map(([_, v], i) => {
      const a = -Math.PI / 2 + (2 * Math.PI * i) / n;
      const rr = r * Math.max(0, Math.min(1, v));
      return `${(cx + rr * Math.cos(a)).toFixed(1)},${(cy + rr * Math.sin(a)).toFixed(1)}`;
    }).join(' ');
    svg += `<polygon points="${dataPts}" fill="rgba(79,70,229,.2)" stroke="#4F46E5" stroke-width="2"/>`;
    entries.forEach(([label], i) => {
      const a = -Math.PI / 2 + (2 * Math.PI * i) / n;
      const tx = cx + (r + 20) * Math.cos(a), ty = cy + (r + 20) * Math.sin(a);
      svg += `<text x="${tx.toFixed(0)}" y="${ty.toFixed(0)}" text-anchor="middle" dominant-baseline="middle" font-size="11" fill="#0f172a">${escapeHtml(label)}</text>`;
    });
    container.innerHTML = `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">${svg}</svg>`;
  }

  function renderDonutChart(container, entries) {
    const colors = ['#4F46E5', '#10B981', '#F59E0B', '#EF4444', '#7C3AED', '#06B6D4', '#84CC16', '#F97316'];
    const total = entries.reduce((s, [_, v]) => s + v, 0) || 1;
    const size = 200, cx = size / 2, cy = size / 2, outer = 80, inner = 50;
    let currentAngle = -Math.PI / 2, paths = '', legend = '';
    entries.forEach(([label, value], i) => {
      const angle = (value / total) * 2 * Math.PI;
      const x1 = cx + outer * Math.cos(currentAngle), y1 = cy + outer * Math.sin(currentAngle);
      const x2 = cx + outer * Math.cos(currentAngle + angle), y2 = cy + outer * Math.sin(currentAngle + angle);
      const x3 = cx + inner * Math.cos(currentAngle + angle), y3 = cy + inner * Math.sin(currentAngle + angle);
      const x4 = cx + inner * Math.cos(currentAngle), y4 = cy + inner * Math.sin(currentAngle);
      const large = angle > Math.PI ? 1 : 0;
      paths += `<path d="M${x1.toFixed(1)} ${y1.toFixed(1)} A${outer} ${outer} 0 ${large} 1 ${x2.toFixed(1)} ${y2.toFixed(1)} L${x3.toFixed(1)} ${y3.toFixed(1)} A${inner} ${inner} 0 ${large} 0 ${x4.toFixed(1)} ${y4.toFixed(1)} Z" fill="${colors[i % colors.length]}" stroke="#fff" stroke-width="2"/>`;
      legend += `<span style="display:inline-flex;align-items:center;gap:4px;font-size:11px;margin:2px 8px;"><span style="width:10px;height:10px;background:${colors[i % colors.length]};border-radius:2px;display:inline-block;"></span>${escapeHtml(label)} ${(value / total * 100).toFixed(0)}%</span>`;
      currentAngle += angle;
    });
    container.innerHTML = `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">${paths}</svg><div style="text-align:center;margin-top:8px;">${legend}</div>`;
  }

  // ========== 练习网格 ==========
  async function renderPracticeGrid(profile) {
    const area = dom.profilePracticeArea; if (!area) return;
    const items = await loadKnowledgePointsCached();
    const abilities = profile?.abilities || {};
    if (!items.length) { area.innerHTML = ''; return; }
    area.innerHTML = `<h3 style="margin:16px 0 8px;">按知识点练习</h3><div class="kp-practice-grid">${items.map(kp => {
      const lv = abilities[kp];
      const pct = typeof lv === 'number' ? Math.round(Math.max(0, Math.min(1, lv)) * 100) : 0;
      const color = pct >= 80 ? 'var(--color-success)' : pct >= 50 ? 'var(--color-warning)' : 'var(--color-danger)';
      return `<div class="kp-practice-item">
        <div class="kp-practice-bar-wrap">
          <span style="font-size:12px;color:var(--color-text);">${escapeHtml(kp)}</span>
          <div class="kp-practice-bar"><div class="kp-practice-bar-fill" style="width:${pct}%;background:${color};"></div></div>
        </div>
        <button class="btn btn-outline btn-sm" onclick="window.__DS.navigateTo('exam');setTimeout(()=>{const cbs=document.querySelectorAll('#kpFilterList input');if(cbs)cbs.forEach(c=>c.checked=c.value==='${escapeHtml(kp).replace(/'/g,"\\'")}');document.getElementById('examStartBtn')?.click()},400);">练习</button>
      </div>`;
    }).join('')}</div>`;
  }

  // ========== AI 评语 ==========
  function renderAiAnalysis(analysis) {
    const area = dom.profileAnalysisArea; if (!area || !analysis) return;
    area.innerHTML = `<div class="ai-analysis-card">
      <div class="ai-analysis-header"><img src="assets/girl.png" class="ai-analysis-avatar" alt="AI"><strong>AI 学习评语</strong></div>
      <div class="ai-analysis-content">${escapeHtml(String(analysis))}</div>
    </div>`;
  }

  // ========== 暴露到 DS ==========
  DS.Profile = { load };
})();
