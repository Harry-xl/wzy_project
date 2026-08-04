/**
 * StarPal Dashboard v2.1 — 主入口 + 共享状态
 * 模块拆分: exam / profile / wrong / chat / admin
 */
'use strict';

// ==================== 全局共享命名空间 ====================
window.__DS = {
  // DOM 工具
  $: (s) => document.querySelector(s),
  $$: (s) => document.querySelectorAll(s),

  // 用户
  userName: storageManager.getCurrentUserName(),
  userId: storageManager.getCurrentUserId(),

  // 缓存
  profileCache: { data: null, ts: 0, ttl: 16 * 60 * 1000 },
  kpCache: { items: null, ts: 0, ttl: 30 * 60 * 1000 },

  // Markdown 渲染器
  msgRenderer: (typeof MessageRenderer !== 'undefined') ? new MessageRenderer() : null,

  // 工具
  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text == null ? '' : String(text);
    return div.innerHTML;
  },
  mapStrength(v) {
    const val = Math.max(0, Math.min(1, Number(v) || 0));
    if (val < 0.4) return { label: '初级', color: '#EF4444' };
    if (val < 0.7) return { label: '中级', color: '#F59E0B' };
    if (val < 0.9) return { label: '高级', color: '#10B981' };
    return { label: '专家', color: '#7C3AED' };
  },
  navigateTo(sectionName) {
    const { $, $$ } = window.__DS;
    $$('.nav-item[data-section]').forEach(n => n.classList.remove('active'));
    const nav = $(`.nav-item[data-section="${sectionName}"]`);
    if (nav) { nav.classList.add('active'); nav.click(); }
  },

  // 公共 DOM
  dom: {}
};

(function () {
  const { $, $$, userName, userId } = window.__DS;
  const DS = window.__DS;

  // ==================== 登录校验 ====================
  if (!storageManager.isLoggedIn() || !userId) {
    Utils.showToast('请先登录', 1500);
    setTimeout(() => { window.location.href = 'login.html'; }, 800);
    return;
  }

  // ==================== 缓存 DOM ====================
  const dom = DS.dom;
  dom.sidebar = $('#sidebar');
  dom.mainContent = $('#mainContent');
  dom.topbarTitle = $('#topbarTitle');
  dom.topbarUserName = $('#topbarUserName');
  dom.topbarAvatar = $('#topbarAvatar');
  dom.strengthBadge = $('#strengthBadge');
  dom.problemsContainer = $('#problemsContainer');
  dom.kpFilterList = $('#kpFilterList');
  dom.profileChartArea = $('#profileChartArea');
  dom.profilePracticeArea = $('#profilePracticeArea');
  dom.profileAnalysisArea = $('#profileAnalysisArea');
  dom.strengthRing = $('#strengthRing');
  dom.strengthTrend = $('#strengthTrend');
  dom.wrongList = $('#wrongList');
  dom.chatBody = $('#chatBody');
  dom.chatEmpty = $('#chatEmpty');
  dom.chatInput = $('#chatInput');

  // 顶栏
  dom.topbarUserName.textContent = userName || '用户';
  const savedAvatar = localStorage.getItem('userAvatar');
  if (savedAvatar) dom.topbarAvatar.src = savedAvatar;

  // 侧边栏折叠
  $('#sidebarToggle').addEventListener('click', () => {
    dom.sidebar.classList.toggle('collapsed');
    dom.mainContent.classList.toggle('expanded');
    const icon = $('#sidebarToggle').querySelector('i');
    icon.className = dom.sidebar.classList.contains('collapsed') ? 'ri-menu-unfold-line' : 'ri-menu-fold-line';
  });

  // 退出
  $('#sidebarLogout').addEventListener('click', () => {
    storageManager.clearCurrentUser();
    window.location.href = 'login.html';
  });

  // ==================== 顶栏实力 ====================
  function updateTopbarStrength() {
    try {
      apiClient.getUserProfile(userId).then(r => {
        if (r && r.success && r.profile) {
          const s = r.profile.user_strength;
          if (typeof s === 'number') {
            const { label, color } = DS.mapStrength(s);
            dom.strengthBadge.textContent = label;
            dom.strengthBadge.style.background = color + '20';
            dom.strengthBadge.style.color = color;
          }
        }
      }).catch(() => { });
    } catch (_) { }
  }
  updateTopbarStrength();

  // ==================== 模块切换 ====================
  const sectionTitles = { exam: '智能做题', profile: '能力画像', wrong: '错题本', chat: 'AI 伴学', admin: '题目管理', bookmarks: '收藏夹' };

  $$('.nav-item[data-section]').forEach(item => {
    item.addEventListener('click', () => {
      const sec = item.dataset.section;
      $$('.nav-item[data-section]').forEach(n => n.classList.remove('active'));
      item.classList.add('active');
      $$('.page-section').forEach(s => { s.style.display = 'none'; s.classList.remove('active'); });

      const target = $(`#section-${sec}`);
      if (target) { target.style.display = 'block'; target.classList.add('active'); }
      dom.topbarTitle.textContent = sectionTitles[sec] || sec;

      // 触发模块初始化
      if (sec === 'exam' && DS.Exam) DS.Exam.init();
      if (sec === 'profile' && DS.Profile) DS.Profile.load();
      if (sec === 'wrong' && DS.Wrong) DS.Wrong.load();
      if (sec === 'admin' && DS.Admin) { DS.Admin.loadProblems(); DS.Admin.loadStats(); DS.Admin.loadKpOptions(); }
      if (sec === 'bookmarks' && DS.Bookmarks) DS.Bookmarks.render();

      if (sec === 'admin') {
        $$('#section-admin .page-section').forEach(s => s.style.display = 'none');
        $('#admin-manage').style.display = 'block';
        $$('.admin-tab').forEach(t => t.classList.remove('active'));
        const first = $('.admin-tab[data-admin-tab="admin-manage"]');
        if (first) first.classList.add('active');
      }
    });
  });

  // 管理后台内部 Tab
  $$('.admin-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      $$('.admin-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const tid = tab.dataset.adminTab;
      ['admin-manage', 'admin-import', 'admin-stats'].forEach(id => {
        const el = $('#' + id); if (el) el.style.display = id === tid ? 'block' : 'none';
      });
      if (tid === 'admin-stats' && DS.Admin) DS.Admin.loadStats();
      if (tid === 'admin-manage' && DS.Admin) DS.Admin.loadProblems();
    });
  });

  // ==================== 全局刷新画像按钮 ====================
  $('#profileRefreshBtn')?.addEventListener('click', () => {
    DS.profileCache.ts = 0;
    if (DS.Profile) DS.Profile.load();
  });

  // ==================== 启动模块 ====================
  if (DS.Exam) DS.Exam.init();
  if (DS.Chat) DS.Chat.init();
})();
