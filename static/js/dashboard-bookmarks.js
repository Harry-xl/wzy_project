/**
 * StarPal — 收藏夹模块
 * localStorage 存储, 支持查看/移除/跳转练习
 */
(function () {
  const DS = window.__DS;
  if (!DS) return;
  const { $, escapeHtml } = DS;
  const STORAGE_KEY = 'starpal_bookmarks';

  function getBookmarks() {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]'); } catch (_) { return []; }
  }

  function render() {
    const container = $('#bookmarksContainer');
    if (!container) return;
    const bookmarks = getBookmarks();
    if (!bookmarks.length) {
      container.innerHTML = `<div class="empty-state">
        <div class="empty-state-icon"><i class="ri-star-line"></i></div>
        <div class="empty-state-title">收藏夹为空</div>
        <div class="empty-state-desc">做题时点击题目卡片上的 ⭐ 按钮即可收藏</div>
      </div>`;
      return;
    }
    container.innerHTML = `<p class="text-sm text-muted" style="margin-bottom:12px;">共收藏 ${bookmarks.length} 道题目</p>` +
      bookmarks.map((p, i) => `
        <div class="wrong-card" style="border-left:4px solid #F59E0B;">
          <div class="wrong-card-header">
            <span class="badge badge-primary">#${escapeHtml(p.problem_num || p.problem_id)}</span>
            <span class="badge badge-warning">${escapeHtml(p.knowledge_point || '未知')}</span>
            <span class="badge ${p.difficulty === '简单' ? 'badge-success' : p.difficulty === '困难' ? 'badge-danger' : 'badge-warning'}">${escapeHtml(p.difficulty || '')}</span>
          </div>
          <div class="problem-stem">${escapeHtml((p.problem || '').substring(0, 200))}${(p.problem || '').length > 200 ? '...' : ''}</div>
          <div style="margin-top:8px;display:flex;gap:8px;">
            <button class="btn btn-outline btn-sm" onclick="window.__DS.Bookmarks._practice(${i})"><i class="ri-play-circle-line"></i> 练习此题</button>
            <button class="btn btn-outline btn-sm" onclick="window.__DS.Bookmarks._practiceByKp('${escapeHtml(p.knowledge_point || '').replace(/'/g,"\\'")}')">同知识点练</button>
            <button class="btn btn-danger btn-sm" onclick="window.__DS.Bookmarks._remove(${i})"><i class="ri-delete-bin-line"></i> 取消收藏</button>
          </div>
        </div>`).join('');
  }

  DS.Bookmarks = {
    render,
    _remove(idx) {
      const bookmarks = getBookmarks();
      bookmarks.splice(idx, 1);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(bookmarks));
      Utils.showToast('已取消收藏');
      render();
    },
    _practice(idx) {
      const bookmarks = getBookmarks();
      if (DS.Exam) DS.Exam.setProblems([bookmarks[idx]]);
      DS.navigateTo('exam');
    },
    _practiceByKp(kp) {
      DS.navigateTo('exam');
      setTimeout(async () => {
        const container = $('#problemsContainer');
        if (container) container.innerHTML = '<div class="empty-state"><div class="skeleton" style="height:120px;"></div></div>';
        try {
          const resp = await apiClient.getProblemsByFilter(DS.userId, 10, { knowledgePoints: [kp], staleDays: 30 });
          if (resp?.success && DS.Exam) DS.Exam.setProblems(resp.problems || []);
        } catch (_) { }
      }, 300);
    }
  };
})();
