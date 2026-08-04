/**
 * StarPal — 做题模块
 * 选题 / 渲染 / 提交答案 / 自动滚动 / 收藏
 */
(function () {
  const DS = window.__DS;
  if (!DS) return;
  const { $, $$, escapeHtml, userId } = DS;
  const dom = DS.dom;

  // 模块状态
  let currentProblems = [], answeredCount = 0, correctCount = 0;

  function parseCount() {
    const raw = ($('#countInput')?.value || '5').trim();
    const n = parseInt(raw.replace(/[^0-9]/g, '')) || 5;
    return Math.max(1, Math.min(50, n));
  }
  function getSelectedKps() {
    if (!dom.kpFilterList) return [];
    return Array.from(dom.kpFilterList.querySelectorAll('input:checked')).map(cb => cb.value);
  }

  // 收藏管理
  function getBookmarks() {
    try { return JSON.parse(localStorage.getItem('starpal_bookmarks') || '[]'); } catch (_) { return []; }
  }
  function saveBookmarks(arr) { localStorage.setItem('starpal_bookmarks', JSON.stringify(arr)); }
  function toggleBookmark(problem) {
    const bookmarks = getBookmarks();
    const idx = bookmarks.findIndex(b => b.problem_id === problem.problem_id);
    if (idx >= 0) { bookmarks.splice(idx, 1); Utils.showToast('已取消收藏'); }
    else { bookmarks.push(problem); Utils.showToast('已加入收藏夹 ⭐'); }
    saveBookmarks(bookmarks);
    updateBookmarkIcons();
  }
  function updateBookmarkIcons() {
    const bookmarks = getBookmarks();
    const bmIds = new Set(bookmarks.map(b => b.problem_id));
    document.querySelectorAll('.bookmark-btn').forEach(btn => {
      const pid = parseInt(btn.dataset.pid);
      const icon = btn.querySelector('i');
      if (bmIds.has(pid)) { icon.className = 'ri-star-fill'; btn.style.color = '#F59E0B'; }
      else { icon.className = 'ri-star-line'; btn.style.color = ''; }
    });
  }

  // ========== 初始化 ==========
  function init() {
    loadKnowledgePoints();
    bindEvents();
  }

  function bindEvents() {
    $('#quickCounts')?.addEventListener('click', e => {
      const btn = e.target.closest('.quick-count-btn');
      if (!btn) return;
      $$('#quickCounts .quick-count-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const ci = $('#countInput'); if (ci) ci.value = btn.dataset.n;
    });
    $('#kpToggleAll')?.addEventListener('click', () => {
      const cbs = dom.kpFilterList?.querySelectorAll('input');
      if (!cbs) return;
      const allChecked = Array.from(cbs).every(c => c.checked);
      cbs.forEach(c => { c.checked = !allChecked; });
      updateKpCount();
    });
    $('#examStartBtn')?.addEventListener('click', loadProblems);
    $('#examSubmitAllBtn')?.addEventListener('click', submitAllAnswers);
    $('#examProfileBtn')?.addEventListener('click', () => {
      DS.navigateTo('profile');
    });
  }

  async function loadKnowledgePoints() {
    try {
      const resp = await apiClient.getKnowledgePoints();
      const items = (resp && resp.success && Array.isArray(resp.items)) ? resp.items : [];
      renderKpTags(items);
    } catch (_) { renderKpTags([]); }
  }

  function renderKpTags(items) {
    if (!dom.kpFilterList) return;
    dom.kpFilterList.innerHTML = '';
    if (!items.length) { dom.kpFilterList.textContent = '暂无知识点'; return; }
    items.forEach(kp => {
      const label = document.createElement('label');
      label.className = 'kp-tag selected';
      label.innerHTML = `<input type="checkbox" value="${escapeHtml(kp)}" checked> ${escapeHtml(kp)}`;
      label.querySelector('input').addEventListener('change', updateKpCount);
      dom.kpFilterList.appendChild(label);
    });
    updateKpCount();
  }

  function updateKpCount() {
    const sel = getSelectedKps();
    const el = $('#kpSelectedCount');
    if (el) el.textContent = `已选 ${sel.length} 个`;
  }

  // ========== 加载题目 ==========
  async function loadProblems() {
    answeredCount = 0; correctCount = 0; currentProblems = [];
    const scr = $('#sessionReportCard'); if (scr) scr.style.display = 'none';
    const count = parseCount();
    if (dom.problemsContainer) dom.problemsContainer.innerHTML = '<div class="empty-state"><div class="skeleton" style="width:100%;height:120px;"></div></div>';

    try {
      const selectedKps = getSelectedKps();
      let resp;
      if (selectedKps.length > 0) {
        resp = await apiClient.getProblemsByFilter(userId, count, { knowledgePoints: selectedKps, staleDays: 30 });
      } else {
        resp = await apiClient.getProblems(userId, count);
      }
      if (!resp || !resp.success) {
        if (dom.problemsContainer) dom.problemsContainer.innerHTML = `<div class="empty-state"><div class="empty-state-title">${resp?.message || '获取题目失败'}</div></div>`;
        return;
      }
      currentProblems = Array.isArray(resp.problems) ? resp.problems : [];
      renderProblems(currentProblems, count);
    } catch (e) {
      if (dom.problemsContainer) dom.problemsContainer.innerHTML = '<div class="empty-state"><div class="empty-state-title">网络错误，请稍后重试</div></div>';
    }
  }

  function parseOptions(text) {
    const lines = text.split('\n');
    const stemLines = [], options = [];
    for (const line of lines) {
      const m = line.match(/^([A-D])\s*[.．]\s*(.+)$/);
      if (m) options.push({ letter: m[1], text: m[2].trim() });
      else stemLines.push(line);
    }
    return { stem: stemLines.join('\n').trim(), options };
  }

  function renderProblems(problems, requestedCount) {
    if (!dom.problemsContainer) return;
    dom.problemsContainer.innerHTML = '';
    if (!problems.length) {
      dom.problemsContainer.innerHTML = '<div class="empty-state"><div class="empty-state-icon"><i class="ri-inbox-line"></i></div><div class="empty-state-title">暂无题目</div><div class="empty-state-desc">试试调整筛选条件或减少题量</div></div>';
      return;
    }
    const progressBar = $('#examProgressBar');
    const progressFill = $('#examProgressFill');
    const progressText = $('#examProgressText');
    if (progressBar) progressBar.style.display = 'flex';
    if (progressFill) progressFill.style.width = '0%';
    if (progressText) progressText.textContent = `已答 0/${problems.length}`;

    const bookmarks = getBookmarks();
    const bmIds = new Set(bookmarks.map(b => b.problem_id));

    problems.forEach(p => {
      const isMC = /[A-D]\.[^\n]/.test(p.problem);
      const card = document.createElement('div');
      card.className = 'problem-card';
      card.id = `prob_${p.problem_id}`;
      const parsed = isMC ? parseOptions(p.problem) : null;

      let answerHTML = '';
      if (isMC && parsed) {
        answerHTML = `<div class="option-list">${parsed.options.map(opt =>
          `<div class="option-item" data-value="${opt.letter}" onclick="this.parentElement.querySelectorAll('.option-item').forEach(e=>e.classList.remove('selected'));this.classList.add('selected');this.querySelector('input').checked=true;">
            <input type="radio" name="mc_${p.problem_id}" value="${opt.letter}"> <label>${opt.letter}. ${escapeHtml(opt.text)}</label>
          </div>`
        ).join('')}</div>`;
      } else {
        answerHTML = `<input class="input" id="ans_${p.problem_id}" placeholder="输入答案" style="width:200px;">`;
      }

      card.innerHTML = `
        <div class="problem-card-result" id="resbar_${p.problem_id}"></div>
        <div class="problem-meta">
          <span class="badge badge-primary">#${p.problem_num || p.problem_id}</span>
          <span class="badge badge-warning">${escapeHtml(p.knowledge_point || '未知')}</span>
          <span class="badge ${p.difficulty === '简单' ? 'badge-success' : p.difficulty === '困难' ? 'badge-danger' : 'badge-warning'}">${p.difficulty || '未知'}</span>
          <button class="bookmark-btn" data-pid="${p.problem_id}" title="收藏" style="margin-left:auto;background:none;border:none;cursor:pointer;font-size:18px;padding:2px 6px;">
            <i class="${bmIds.has(p.problem_id) ? 'ri-star-fill' : 'ri-star-line'}" style="color:${bmIds.has(p.problem_id) ? '#F59E0B' : 'var(--color-text-muted)'};"></i>
          </button>
        </div>
        <div class="problem-stem">${escapeHtml(isMC && parsed ? parsed.stem : p.problem)}</div>
        ${answerHTML}
        <div class="answer-row">
          <button class="btn btn-primary btn-sm" id="btn_${p.problem_id}" onclick="window.__DS.Exam._submitAnswer(${p.problem_id}, '${isMC}')">提交答案</button>
        </div>
        <div class="feedback" id="fb_${p.problem_id}" style="display:none;"></div>
      `;
      dom.problemsContainer.appendChild(card);
    });

    // 收藏按钮事件
    document.querySelectorAll('.bookmark-btn').forEach(btn => {
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        const pid = parseInt(this.dataset.pid);
        const problem = currentProblems.find(p => p.problem_id === pid);
        if (problem) toggleBookmark(problem);
      });
    });
  }

  // ========== 提交答案 + 自动滚动 ==========
  window.__DS.Exam = window.__DS.Exam || {};
  DS.Exam._submitAnswer = async function (problemId, isMC) {
    let val = '';
    if (isMC === 'true') {
      const sel = document.querySelector(`input[name="mc_${problemId}"]:checked`);
      val = sel ? sel.value : '';
    } else {
      const inp = document.getElementById(`ans_${problemId}`);
      val = (inp?.value || '').trim();
    }
    const fb = document.getElementById(`fb_${problemId}`);
    if (!val) {
      if (fb) { fb.style.display = 'block'; fb.className = 'feedback wrong'; fb.textContent = '请先输入/选择答案'; }
      return;
    }
    const btn = document.getElementById(`btn_${problemId}`);
    if (btn) { btn.disabled = true; btn.textContent = '提交中...'; }
    try {
      const resp = await apiClient.submitAnswer(userId, problemId, val);
      const bar = document.getElementById(`resbar_${problemId}`);
      const card = document.getElementById(`prob_${problemId}`);
      if (resp && resp.success) {
        if (resp.is_correct) {
          if (fb) { fb.className = 'feedback correct'; fb.textContent = '✓ 回答正确！'; fb.style.display = 'block'; }
          if (bar) bar.className = 'problem-card-result show correct';
          if (card) card.classList.add('correct');
          correctCount++;
        } else {
          if (fb) { fb.className = 'feedback wrong'; fb.textContent = `✗ 回答错误，正确答案：${resp.correct_answer}`; fb.style.display = 'block'; }
          if (bar) bar.className = 'problem-card-result show wrong';
          if (card) card.classList.add('wrong');
        }
        if (btn && !btn.dataset.done) { answeredCount++; btn.dataset.done = '1'; }
        updateProgress();

        // ★ 自动滚动到下一未答题
        scrollToNextUnanswered(problemId);

        if (answeredCount >= currentProblems.length) generateSessionReport();
      }
    } catch (e) {
      if (fb) { fb.style.display = 'block'; fb.className = 'feedback wrong'; fb.textContent = '提交失败'; }
    }
    if (btn) { btn.disabled = true; btn.textContent = '已提交'; }
  };

  /** 自动滚动到下一道未做的题目 */
  function scrollToNextUnanswered(currentPid) {
    const allCards = document.querySelectorAll('.problem-card');
    let found = false;
    for (const card of allCards) {
      const cardBtn = card.querySelector('button[id^="btn_"]');
      if (cardBtn && !cardBtn.disabled) {
        card.scrollIntoView({ behavior: 'smooth', block: 'center' });
        // 聚焦输入框或第一个选项
        const input = card.querySelector('input[type="text"], input[type="radio"]');
        if (input) setTimeout(() => input.focus(), 400);
        found = true;
        break;
      }
    }
    if (!found) {
      // 全部答完，滚动到报告区
      const report = $('#sessionReportCard');
      if (report && report.style.display !== 'none') report.scrollIntoView({ behavior: 'smooth' });
    }
  }

  async function submitAllAnswers() {
    const tasks = [];
    for (const p of currentProblems) {
      const btn = document.getElementById(`btn_${p.problem_id}`);
      if (btn?.disabled) continue;
      const isMC = /[A-D]\.[^\n]/.test(p.problem);
      let val = '';
      if (isMC) {
        const sel = document.querySelector(`input[name="mc_${p.problem_id}"]:checked`);
        val = sel ? sel.value : '';
      } else {
        const inp = document.getElementById(`ans_${p.problem_id}`);
        val = (inp?.value || '').trim();
      }
      if (!val) continue;
      tasks.push({ p, val, btn });
    }
    if (!tasks.length) { Utils.showToast('没有可提交的答案'); return; }
    const results = await Promise.allSettled(tasks.map(t => apiClient.submitAnswer(userId, t.p.problem_id, t.val)));
    results.forEach((r, i) => {
      const { p, btn } = tasks[i];
      const fb = document.getElementById(`fb_${p.problem_id}`);
      const bar = document.getElementById(`resbar_${p.problem_id}`);
      const card = document.getElementById(`prob_${p.problem_id}`);
      if (r.status === 'fulfilled' && r.value?.success) {
        if (r.value.is_correct) { if (fb) { fb.className = 'feedback correct'; fb.textContent = '✓ 回答正确！'; fb.style.display = 'block'; } if (bar) bar.className = 'problem-card-result show correct'; if (card) card.classList.add('correct'); correctCount++; }
        else { if (fb) { fb.className = 'feedback wrong'; fb.textContent = `✗ 错误，正确答案：${r.value.correct_answer}`; fb.style.display = 'block'; } if (bar) bar.className = 'problem-card-result show wrong'; if (card) card.classList.add('wrong'); }
        if (btn && !btn.dataset.done) { answeredCount++; btn.dataset.done = '1'; btn.disabled = true; btn.textContent = '已提交'; }
      }
    });
    updateProgress();
    if (answeredCount >= currentProblems.length) generateSessionReport();
  }

  function updateProgress() {
    const fill = $('#examProgressFill');
    const text = $('#examProgressText');
    const total = currentProblems.length;
    if (fill) fill.style.width = total ? (answeredCount / total * 100) + '%' : '0%';
    if (text) text.textContent = `已答 ${answeredCount}/${total}`;
  }

  function generateSessionReport() {
    const total = currentProblems.length;
    const acc = total ? Math.round(correctCount / total * 100) : 0;
    const color = acc >= 80 ? 'var(--color-success)' : acc >= 50 ? 'var(--color-warning)' : 'var(--color-danger)';
    const el = $('#sessionReport');
    const card = $('#sessionReportCard');
    if (!el || !card) return;
    el.innerHTML = `
      <div class="session-report-stats">
        <div class="session-stat"><div class="session-stat-value">${total}</div><div class="session-stat-label">总题数</div></div>
        <div class="session-stat"><div class="session-stat-value ok">${correctCount}</div><div class="session-stat-label">正确</div></div>
        <div class="session-stat"><div class="session-stat-value" style="color:${color}">${acc}%</div><div class="session-stat-label">正确率</div></div>
      </div>
      <p style="margin-top:12px;color:var(--color-text-secondary);font-size:var(--font-size-sm);">
        ${acc >= 80 ? '👍 表现优秀！继续保持。' : acc >= 50 ? '📚 还有提升空间，建议关注错题本。' : '💪 需要多加练习，试试查看 AI 讲解。'}
      </p>`;
    card.style.display = '';
    card.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  // ========== 暴露到 DS ==========
  DS.Exam = {
    init,
    loadProblems,
    renderProblems,
    _submitAnswer: DS.Exam._submitAnswer,
    getProblems: () => currentProblems,
    setProblems(problems) {
      currentProblems = problems.map(p => ({
        problem_id: Number(p.problem_id), problem_num: p.problem_num,
        problem: p.problem, answer: p.answer, difficulty: p.difficulty, knowledge_point: p.knowledge_point
      }));
      answeredCount = 0; correctCount = 0;
      const scr = $('#sessionReportCard'); if (scr) scr.style.display = 'none';
      renderProblems(currentProblems, currentProblems.length);
    }
  };
})();
