/**
 * StarPal 我的资料库 — 知识清单 + 覆盖度
 * 双 Tab: 按知识点 / 按资料
 */
'use strict';

(function () {
  const DS = window.__DS;
  if (!DS) return;

  DS.LibraryKnowledge = {
    _coverageData: null,

    async loadCoverage() {
      try {
        const resp = await fetch(`http://127.0.0.1:3001/api/library/knowledge-coverage?user_id=${DS.userId || 0}`);
        const data = await resp.json();
        if (!data.success) return;
        this._coverageData = data.coverage;
        this.renderCoverageRing();
        this.renderKnowledgeTable();
        this.loadDocView();
      } catch (_) { }
    },

    renderCoverageRing() {
      const cov = this._coverageData;
      if (!cov) return;
      const container = DS.$('#libraryCoverageRing');
      if (!container) return;

      const pct = cov.coverage_pct || 0;
      container.innerHTML = `
        <div style="text-align:center;">
          <svg width="120" height="120" viewBox="0 0 120 120">
            <circle cx="60" cy="60" r="50" fill="none" stroke="var(--color-border)" stroke-width="10"/>
            <circle cx="60" cy="60" r="50" fill="none" stroke="${pct >= 50 ? '#22C55E' : pct > 0 ? '#F59E0B' : '#9CA3AF'}" stroke-width="10"
              stroke-dasharray="${pct * 3.14}" stroke-dashoffset="0" transform="rotate(-90 60 60)" stroke-linecap="round"/>
            <text x="60" y="55" text-anchor="middle" font-size="20" font-weight="700" fill="var(--color-text)">${pct}%</text>
            <text x="60" y="72" text-anchor="middle" font-size="10" fill="var(--color-text-secondary)">${cov.covered_count}/${cov.total_sub_topics}</text>
          </svg>
          <div style="font-size:var(--font-size-sm);color:var(--color-text-secondary);margin-top:var(--space-sm);">知识点覆盖率</div>
        </div>
      `;
    },

    renderKnowledgeTable(filterKp = '') {
      const cov = this._coverageData;
      if (!cov || !cov.details) return;
      const container = DS.$('#libraryKnowledgeTable');
      if (!container) return;

      let details = cov.details;
      if (filterKp) { details = details.filter(d => d.parent_kp === filterKp); }

      // 收集所有 parent_kp 用于筛选下拉
      const kpSet = new Set(cov.details.map(d => d.parent_kp));
      const filterEl = DS.$('#libraryKpFilter');
      if (filterEl && filterEl.options.length <= 1) {
        filterEl.innerHTML = '<option value="">全部知识点大类</option>' +
          [...kpSet].sort().map(k => `<option value="${DS.escapeHtml(k)}">${DS.escapeHtml(k)}</option>`).join('');
        filterEl.addEventListener('change', () => this.renderKnowledgeTable(filterEl.value));
      }

      container.innerHTML = details.map(d => {
        const statusClass = d.status === 'covered' ? 'covered' : 'uncovered';
        const statusText = d.status === 'covered' ? `${d.doc_count}份·${d.chunk_count}块` : '—';
        return `
          <div class="library-kp-row" data-tid="${d.sub_topic_id}">
            <span class="library-kp-name">${DS.escapeHtml(d.sub_topic_name)} <span style="color:var(--color-text-muted);font-size:11px;">${DS.escapeHtml(d.parent_kp)}</span></span>
            <span class="library-kp-status ${statusClass}">${statusText}</span>
          </div>
          <div class="library-kp-expand" id="kpExpand${d.sub_topic_id}"></div>
        `;
      }).join('');

      // 点击打开学习卡片
      container.querySelectorAll('.library-kp-row').forEach(row => {
        row.addEventListener('click', async () => {
          const tid = parseInt(row.dataset.tid);
          if (!tid) return;
          // 打开学习卡片（替代旧的下钻面板）
          if (DS.LearningCardModal) {
            DS.LearningCardModal.open(tid);
          }
        });
      });

      // 为每个子知识点添加"学习"按钮
      container.querySelectorAll('.library-kp-row').forEach(row => {
        // 给行添加视觉提示：可点击
        row.style.cursor = 'pointer';
        row.title = '点击查看学习卡片';
      });
    },

    loadDocView() {
      const container = DS.$('#libraryDocCoverage');
      if (!container) return;

      // 从文档列表接口获取文档信息并展示
      (async () => {
        try {
          const resp = await fetch(`http://127.0.0.1:3001/api/library/documents?user_id=${DS.userId || 0}`);
          const data = await resp.json();
          if (!data.success || !data.documents?.length) {
            container.innerHTML = '<div class="library-empty"><p>暂无资料</p></div>';
            return;
          }
          // 为每份资料展示简要信息
          container.innerHTML = data.documents.map(d => `
            <div class="library-doc-card">
              <i class="ri-file-text-line library-doc-icon"></i>
              <div class="library-doc-info">
                <div class="library-doc-title">${DS.escapeHtml(d.title||'')}</div>
                <div class="library-doc-meta">${d.doc_type||''} · ${d.chunk_count||0} 个知识块 · ${(d.created_at||'').slice(0,10)}</div>
              </div>
            </div>
          `).join('');
        } catch (_) { }
      })();
    },
  };
})();
