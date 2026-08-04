/**
 * StarPal — 错题本模块
 */
(function () {
  const DS = window.__DS;
  if (!DS) return;
  const { $, escapeHtml, userId } = DS;

  let wrongPager = { offset: 0, pageSize: 20, busy: false, done: false };
  let wrongKpOptions = [];

  function load() {
    wrongPager.offset = 0; wrongPager.done = false;
    fetchWrong();
  }

  function bindEvents() {
    $('#wrongLoadBtn')?.addEventListener('click', load);
    $('#wrongSortSelect')?.addEventListener('change', () => { wrongPager.offset = 0; wrongPager.done = false; fetchWrong(); });
    $('#wrongStartRedoBtn')?.addEventListener('click', startWrongRedo);
    $('#wrongRedoMode')?.addEventListener('change', function () {
      const kpSel = $('#wrongRedoKp'); if (kpSel) kpSel.style.display = this.value === 'knowledge_point' ? '' : 'none';
    });
    // 加载更多按钮委托
    document.addEventListener('click', e => {
      if (e.target.id === 'wrongLoadMoreBtn') loadMore();
    });
    // 错题卡中按钮事件委托
    document.getElementById('wrongList')?.addEventListener('click', e => {
      const card = e.target.closest('.wrong-card');
      if (!card) return;
      if (e.target.closest('.redo-exact')) {
        const pid = e.target.closest('.redo-exact').dataset.pid;
        reQuizExact([{ problem_id: pid, problem: '', answer: '', difficulty: '', knowledge_point: '' }]);
      }
      if (e.target.closest('.redo-kp')) {
        const kp = e.target.closest('.redo-kp').dataset.kp;
        DS.navigateTo('exam');
        setTimeout(async () => {
          const container = $('#problemsContainer'); if (container) container.innerHTML = '<div class="empty-state"><div class="skeleton" style="height:120px;"></div></div>';
          try { const resp = await apiClient.getProblemsByFilter(userId, 10, { knowledgePoints: [kp], staleDays: 30 }); if (resp?.success && DS.Exam) DS.Exam.setProblems(resp.problems || []); } catch (_) { }
        }, 300);
      }
      if (e.target.closest('.redo-diff')) {
        const diff = e.target.closest('.redo-diff').dataset.diff;
        DS.navigateTo('exam');
        setTimeout(async () => {
          const container = $('#problemsContainer'); if (container) container.innerHTML = '<div class="empty-state"><div class="skeleton" style="height:120px;"></div></div>';
          try { const resp = await apiClient.getProblemsByFilter(userId, 10, { difficulties: [diff], staleDays: 30 }); if (resp?.success && DS.Exam) DS.Exam.setProblems(resp.problems || []); } catch (_) { }
        }, 300);
      }
      if (e.target.closest('.btn-explain-wrong')) streamExplainForWrong(e.target.closest('.btn-explain-wrong'));
      if (e.target.closest('.stop-explain-wrong')) stopExplainForWrong(e.target.closest('.stop-explain-wrong'));
    });
  }

  async function fetchWrong() {
    wrongPager.busy = true;
    const limitVal = parseInt($('#wrongLimitInput')?.value || '20');
    wrongPager.pageSize = isFinite(limitVal) ? Math.max(1, Math.min(200, limitVal)) : 20;
    const sortBy = $('#wrongSortSelect')?.value || 'time';
    const list = $('#wrongList'); if (list) list.innerHTML = '<div class="skeleton" style="height:120px;"></div>';
    try {
      const resp = await apiClient.getWrongAnswers(userId, wrongPager.pageSize, 0, sortBy);
      if (!resp?.success) { if (list) list.textContent = resp?.message || '加载失败'; return; }
      const items = resp.items || [];
      wrongPager.offset = items.length;
      wrongPager.done = items.length < wrongPager.pageSize;
      renderList(items, false);
      updateKpOptions(items);
    } catch (e) { if (list) list.textContent = '加载失败'; }
    finally { wrongPager.busy = false; updateLoadMoreBtn(); }
  }

  async function loadMore() {
    if (wrongPager.busy || wrongPager.done) return;
    wrongPager.busy = true; updateLoadMoreBtn();
    const sortBy = $('#wrongSortSelect')?.value || 'time';
    try {
      const resp = await apiClient.getWrongAnswers(userId, wrongPager.pageSize, wrongPager.offset, sortBy);
      if (!resp?.success) return;
      const items = resp.items || [];
      wrongPager.offset += items.length;
      if (items.length < wrongPager.pageSize) wrongPager.done = true;
      renderList(items, true);
      updateKpOptions(items, true);
    } catch (_) { } finally { wrongPager.busy = false; updateLoadMoreBtn(); }
  }

  function renderList(items, append) {
    const list = $('#wrongList'); if (!list) return;
    if (!append) list.innerHTML = '';
    if (!items.length && !append) { list.innerHTML = '<div class="empty-state"><div class="empty-state-icon"><i class="ri-emotion-happy-line"></i></div><div class="empty-state-title">暂无错题</div><div class="empty-state-desc">继续做题，错题会自动收录</div></div>'; return; }
    if (!items.length && append) { wrongPager.done = true; updateLoadMoreBtn(); return; }
    const frag = document.createDocumentFragment();
    items.forEach(r => {
      const card = document.createElement('div');
      card.className = `wrong-card diff-${r.difficulty || '简单'}`;
      const timeStr = r.answer_time ? String(r.answer_time).replace('T', ' ').split('.')[0] : '';
      card.innerHTML = `
        <div class="wrong-card-header">
          <span class="badge badge-primary">#${r.problem_num || r.problem_id}</span>
          <span class="badge badge-warning">${escapeHtml(r.knowledge_point || '未知')}</span>
          <span class="badge ${r.difficulty === '简单' ? 'badge-success' : r.difficulty === '困难' ? 'badge-danger' : 'badge-warning'}">${r.difficulty || ''}</span>
          <span style="font-size:11px;color:var(--color-text-muted);">${timeStr}</span>
          <span style="font-size:11px;color:var(--color-danger);">错${r.redo_wrong_count || 0}次</span>
        </div>
        <div class="problem-stem">${escapeHtml((r.problem || '').substring(0, 200))}${(r.problem || '').length > 200 ? '...' : ''}</div>
        <div class="answer-compare">
          <span class="answer-chip bad">你的答案：${escapeHtml(r.user_answer || '')}</span>
          <span class="answer-chip ok">正确答案：${escapeHtml(r.answer || '')}</span>
        </div>
        <div class="wrong-card-actions">
          <button class="btn btn-outline btn-sm redo-exact" data-pid="${r.problem_id}">重做此题</button>
          <button class="btn btn-outline btn-sm redo-kp" data-kp="${escapeHtml(r.knowledge_point || '')}">同知识点练</button>
          <button class="btn btn-outline btn-sm redo-diff" data-diff="${escapeHtml(r.difficulty || '')}">同难度练</button>
          <button class="btn btn-primary btn-sm btn-explain-wrong" data-pid="${r.problem_id}">AI 讲解</button>
          <button class="btn btn-danger btn-sm stop-explain-wrong" style="display:none;">停止</button>
        </div>
        <div class="explain-panel" id="explain_${r.problem_id}"></div>`;
      frag.appendChild(card);
    });
    list.appendChild(frag);
  }

  async function streamExplainForWrong(btn) {
    const card = btn.closest('.wrong-card');
    const panel = card.querySelector('.explain-panel');
    const stopBtn = card.querySelector('.stop-explain-wrong');
    const problemText = card.querySelector('.problem-stem')?.textContent || '';
    btn.style.display = 'none'; stopBtn.style.display = '';
    panel.style.display = 'block'; panel.classList.add('open');
    panel.innerHTML = '<em class="text-muted">正在生成讲解...</em>';
    const controller = new AbortController();
    stopBtn._controller = controller;
    try {
      const stream = await apiClient.explainProblemStream({ problem_text: problemText }, controller.signal);
      if (!stream) { console.error('[explain] 无法获取流，检查Network标签中/api/explain/stream的状态'); panel.textContent = '无法连接'; return; }
      await typewriterRender(stream, panel, controller.signal);
    } catch (e) {
      if (e.name !== 'AbortError') { console.error('[explain] 异常:', e.message || e); panel.textContent = '生成失败'; }
      else panel.innerHTML += '<br><em style="color:var(--color-text-muted);">[已停止]</em>';
    } finally { btn.style.display = ''; stopBtn.style.display = 'none'; }
  }

  function stopExplainForWrong(btn) {
    if (btn._controller) { btn._controller.abort(); btn._controller = null; }
  }

  async function typewriterRender(stream, target, signal) {
    const reader = stream.getReader();
    const decoder = new TextDecoder();
    let buffer = '', displayed = '', sseBuf = '', eventAcc = '';
    target.textContent = '';
    let typing = false;
    const tick = () => {
      if (buffer.length > 0) {
        const take = Math.min(6, buffer.length);
        displayed += buffer.slice(0, take); buffer = buffer.slice(take);
        target.textContent = displayed; setTimeout(tick, 18);
      } else {
        typing = false;  // 缓冲区已空，重置标志以便新内容到达时重新启动打字
      }
    };
    while (true) {
      if (signal?.aborted) { reader.cancel(); break; }
      const { done, value } = await reader.read();
      if (done) { if (eventAcc && eventAcc !== '[DONE]') buffer += eventAcc; if (!typing) { displayed += buffer; buffer = ''; target.textContent = displayed; } break; }
      sseBuf += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = sseBuf.indexOf('\n')) >= 0) {
        let line = sseBuf.slice(0, idx).replace(/\r$/, ''); sseBuf = sseBuf.slice(idx + 1);
        if (line === '') {
          if (eventAcc && eventAcc !== '[DONE]') {
            buffer += eventAcc;
            if (!typing) { typing = true; setTimeout(tick, 0); }
          }
          eventAcc = '';
        }
        else if (line.startsWith('data:')) { let data = line.slice(5).trim(); if (data !== '[DONE]') eventAcc += data; }
      }
    }
    target.textContent = displayed;
  }

  function updateLoadMoreBtn() {
    const wrap = $('#wrongLoadMoreWrap'); if (!wrap) return;
    let btn = $('#wrongLoadMoreBtn');
    if (wrongPager.done) { if (btn) btn.remove(); return; }
    if (!btn) {
      btn = document.createElement('button');
      btn.id = 'wrongLoadMoreBtn';
      btn.className = 'btn btn-outline btn-sm';
      btn.style.display = 'block'; btn.style.margin = '8px auto 0';
      btn.textContent = '加载更多';
      wrap.appendChild(btn);
    }
    btn.textContent = wrongPager.busy ? '加载中...' : '加载更多';
    btn.disabled = wrongPager.busy;
  }

  function updateKpOptions(items, append) {
    const sel = $('#wrongRedoKp'); if (!sel) return;
    if (!append) wrongKpOptions = [];
    items.forEach(r => { if (r.knowledge_point) wrongKpOptions.push(String(r.knowledge_point)); });
    wrongKpOptions = [...new Set(wrongKpOptions)].sort((a, b) => a.localeCompare(b, 'zh'));
    sel.innerHTML = '<option value="">选择知识点</option>' + wrongKpOptions.map(kp => `<option value="${escapeHtml(kp)}">${escapeHtml(kp)}</option>`).join('');
  }

  async function startWrongRedo() {
    const mode = $('#wrongRedoMode')?.value || 'time';
    const count = parseInt($('#wrongRedoCount')?.value || '10');
    const kp = $('#wrongRedoKp')?.value || '';
    try {
      const resp = await apiClient.getWrongRedoProblems(userId, { mode, count: isFinite(count) ? Math.max(1, Math.min(200, count)) : 10, knowledgePoint: kp });
      if (!resp?.success) { Utils.showToast(resp?.message || '获取失败'); return; }
      if (!resp.items?.length) { Utils.showToast('暂无错题可重做'); return; }
      reQuizExact(resp.items);
    } catch (_) { Utils.showToast('获取失败'); }
  }

  function reQuizExact(problems) {
    if (DS.Exam) DS.Exam.setProblems(problems);
    DS.navigateTo('exam');
  }

  // 初始化事件
  bindEvents();

  DS.Wrong = { load, fetchWrong };
})();
