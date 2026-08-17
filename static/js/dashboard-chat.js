/**
 * StarPal — AI 伴学（聊天）模块
 */
(function () {
  const DS = window.__DS;
  if (!DS) return;
  const { $, escapeHtml, userName } = DS;

  let chatControllers = {}, chatStreamCache = {}, currentChatId = null, chatList = [];
  const msgRenderer = DS.msgRenderer;

  function init() {
    chatList = storageManager.getChatList();
    currentChatId = storageManager.getCurrentChatId();
    if (!chatList?.length) {
      const nc = storageManager.createNewChat();
      chatList = storageManager.getChatList();
      currentChatId = nc.id;
      storageManager.setCurrentChatId(currentChatId);
    } else if (!currentChatId || !chatList.find(c => c.id === currentChatId)) {
      currentChatId = chatList[0].id;
      storageManager.setCurrentChatId(currentChatId);
    }
    renderHistoryList();
    renderMessages();
    updateGreeting();
    bindEvents();
  }

  function updateGreeting() {
    const h = new Date().getHours();
    let g = '你好';
    if (h < 11) g = '早上好'; else if (h < 14) g = '中午好'; else if (h < 18) g = '下午好'; else g = '晚上好';
    const el = $('#chatGreeting'); if (el) el.textContent = g + '，' + (userName || '同学') + '！';
  }

  function renderHistoryList() {
    const list = $('#chatHistoryList'); if (!list) return;
    list.innerHTML = chatList.map(c => `
      <div class="chat-thread-item ${c.id === currentChatId ? 'active' : ''}" data-cid="${c.id}">
        <span class="chat-thread-title">${escapeHtml(c.title || '新对话')}</span>
        <span class="chat-thread-time">${new Date(c.time).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })}</span>
        <button class="chat-thread-delete" data-del="${c.id}">&times;</button>
      </div>`).join('');

    list.querySelectorAll('.chat-thread-item').forEach(item => {
      item.addEventListener('click', function (e) {
        if (e.target.closest('.chat-thread-delete')) return;
        currentChatId = this.dataset.cid;
        storageManager.setCurrentChatId(currentChatId);
        renderHistoryList(); renderMessages();
      });
    });
    list.querySelectorAll('.chat-thread-delete').forEach(btn => {
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        if (confirm('删除此对话？')) {
          storageManager.deleteChat(this.dataset.del);
          chatList = storageManager.getChatList();
          currentChatId = chatList.length ? chatList[0].id : null;
          storageManager.setCurrentChatId(currentChatId);
          renderHistoryList(); renderMessages();
        }
      });
    });
  }

  function renderMessages() {
    const body = $('#chatBody'), empty = $('#chatEmpty'); if (!body) return;
    const history = currentChatId ? storageManager.getChatHistory(currentChatId) : [];
    body.querySelectorAll('.message').forEach(m => m.remove());
    if (!history.length) { if (empty) empty.style.display = ''; return; }
    if (empty) empty.style.display = 'none';
    history.forEach((msg, i) => body.appendChild(createMessageEl(msg, i, history)));
    body.scrollTop = body.scrollHeight;
  }

  function createMessageEl(msg, idx, history) {
    const div = document.createElement('div');
    div.className = `message ${msg.role}`;
    const avatarSrc = msg.role === 'user' ? (localStorage.getItem('userAvatar') || 'assets/user-avatar.svg') : 'assets/girl.png';
    div.innerHTML = `<img src="${avatarSrc}" class="message-avatar" alt="">`;
    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    bubble.innerHTML = msgRenderer ? msgRenderer.renderMessageContent(msg.content) : escapeHtml(msg.content);
    div.appendChild(bubble);

    const actions = document.createElement('div');
    actions.className = 'message-actions';
    actions.innerHTML = `<button title="复制" onclick="navigator.clipboard.writeText(\`${msg.content.replace(/`/g, '\\`').replace(/\$/g, '\\$')}\`);Utils.showToast('已复制')"><i class="ri-file-copy-line"></i></button>`;
    if (msg.role === 'ai') actions.innerHTML += `<button title="重新生成" data-regen="${idx}"><i class="ri-refresh-line"></i></button>`;
    if (msg.role === 'user' && idx === history.length - 1) actions.innerHTML += `<button title="编辑" data-edit="${idx}"><i class="ri-edit-line"></i></button>`;
    bubble.appendChild(actions);

    // RAG 来源引用展示
    if (msg.role === 'ai' && msg.sources && msg.sources.length > 0) {
      const sourcesCard = document.createElement('div');
      sourcesCard.className = 'sources-card';
      let sourcesHtml = '<div class="sources-title"><i class="ri-book-open-line"></i> 参考来源</div>';
      msg.sources.forEach(s => {
        const scorePct = s.score ? ` <span class="source-score">相关性 ${Math.round(s.score * 100)}%</span>` : '';
        sourcesHtml += `<div class="source-item"><span class="source-index">${s.index}</span> ${escapeHtml(s.source || '')} · ${escapeHtml(s.title || '')}${s.source_page ? ' · ' + escapeHtml(s.source_page) : ''}${scorePct}</div>`;
      });
      sourcesCard.innerHTML = sourcesHtml;
      bubble.appendChild(sourcesCard);
    }

    div.addEventListener('mouseenter', () => actions.style.opacity = '1');
    div.addEventListener('mouseleave', () => actions.style.opacity = '0');
    return div;
  }

  function sendMessage(msg) {
    if (!currentChatId) {
      const nc = storageManager.createNewChat(); chatList = storageManager.getChatList();
      currentChatId = nc.id; storageManager.setCurrentChatId(currentChatId); renderHistoryList();
    }
    const history = storageManager.getChatHistory(currentChatId);
    history.push({ role: 'user', content: msg, time: Date.now() });
    storageManager.saveChatHistory(currentChatId, history);
    renderMessages();
    streamAiReply(msg);
    const chatObj = chatList.find(c => c.id === currentChatId);
    if (chatObj && (!chatObj.title || chatObj.title === '新对话')) {
      chatObj.title = msg.length > 10 ? msg.slice(0, 10) + '...' : msg;
      storageManager.saveChatList(chatList); renderHistoryList();
    }
  }

  async function streamAiReply(userMsg) {
    const history = storageManager.getChatHistory(currentChatId);
    const aiPlaceholder = { role: 'ai', content: '', time: Date.now() };
    history.push(aiPlaceholder); storageManager.saveChatHistory(currentChatId, history); renderMessages();

    const controller = new AbortController();
    chatControllers[currentChatId] = controller;
    const stopBtn = $('#chatStopBtn'), sendBtn = $('#chatSendBtn');
    if (stopBtn) stopBtn.style.display = 'flex'; if (sendBtn) sendBtn.style.display = 'none';

    try {
      const resp = await apiClient.chatStream(
        userMsg, storageManager.currentUser || userName, currentChatId, null, controller.signal,
        { knowledge_scope: knowledgeScope, user_id: storageManager.getCurrentUserId() || 0 }
      );
      if (!resp.ok) { console.error('[chat] HTTP错误:', resp.status, resp.statusText); finishReply('抱歉，AI 服务暂不可用。'); return; }
      const reader = resp.body.getReader(); const decoder = new TextDecoder();
      let full = '', sseBuf = '', eventAcc = '', sources = null;
      while (true) {
        const { done, value } = await reader.read(); if (done) break;
        sseBuf += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = sseBuf.indexOf('\n')) >= 0) {
          let line = sseBuf.slice(0, idx).replace(/\r$/, ''); sseBuf = sseBuf.slice(idx + 1);
          if (line === '') {
            try {
              const o = JSON.parse(eventAcc);
              if (o.reply !== undefined) { full += o.reply; aiPlaceholder.content = full; }
              if (o.done && o.sources) { sources = o.sources; aiPlaceholder.sources = o.sources; }
              storageManager.saveChatHistory(currentChatId, history);
            } catch (_) { }
            eventAcc = '';
          }
          else if (line.startsWith('data:')) eventAcc += line.slice(5).trim();
        }
        renderMessages(); const cb = $('#chatBody'); if (cb) cb.scrollTop = cb.scrollHeight;
      }
      aiPlaceholder.sources = sources;
      finishReply(full);
    } catch (e) { if (e.name !== 'AbortError') { console.error('[chat] 异常:', e.message || e); finishReply('抱歉，AI 服务暂不可用。'); } }
    finally { if (stopBtn) stopBtn.style.display = 'none'; if (sendBtn) sendBtn.style.display = 'flex'; delete chatControllers[currentChatId]; }
  }

  function finishReply(content) {
    const history = storageManager.getChatHistory(currentChatId);
    const last = history[history.length - 1];
    if (last && last.role === 'ai') {
      last.content = content;
      // 保留 sources（从 aiPlaceholder 传递过来）
      storageManager.saveChatHistory(currentChatId, history);
    }
    renderMessages();
  }

  function bindEvents() {
    $('#chatSendBtn')?.addEventListener('click', () => {
      const input = $('#chatInput'); const msg = (input?.value || '').trim(); if (!msg) return;
      input.value = ''; sendMessage(msg);
    });
    $('#chatInput')?.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); $('#chatSendBtn')?.click(); }
    });
    $('#chatStopBtn')?.addEventListener('click', () => {
      if (chatControllers[currentChatId]) {
        chatControllers[currentChatId].abort();
        const history = storageManager.getChatHistory(currentChatId);
        const last = history[history.length - 1];
        if (last && last.role === 'ai' && last.content) { last.content += '\n\n[已停止生成]'; storageManager.saveChatHistory(currentChatId, history); renderMessages(); }
      }
    });
    $('#chatNewBtn')?.addEventListener('click', () => {
      const nc = storageManager.createNewChat(); chatList = storageManager.getChatList();
      currentChatId = nc.id; storageManager.setCurrentChatId(currentChatId);
      renderHistoryList(); renderMessages();
    });
    $('#chatEmpty')?.addEventListener('click', function (e) {
      const btn = e.target.closest('.chat-suggestion'); if (!btn) return;
      sendMessage(btn.textContent);
    });
    // 侧边栏切换
    const toggle = document.createElement('button');
    toggle.className = 'btn btn-ghost btn-sm';
    toggle.style.cssText = 'position:absolute;left:0;top:50%;z-index:10;';
    toggle.innerHTML = '<i class="ri-menu-line"></i>';
    toggle.title = '展开对话列表';
    toggle.addEventListener('click', () => {
      const sb = $('#chatSidebar'); sb.classList.toggle('open');
      toggle.querySelector('i').className = sb.classList.contains('open') ? 'ri-menu-fold-line' : 'ri-menu-line';
    });
    const mainPanel = document.querySelector('.chat-main-panel');
    if (mainPanel) { mainPanel.style.position = 'relative'; mainPanel.prepend(toggle); }
    // 重新生成/编辑
    $('#chatBody')?.addEventListener('click', function (e) {
      const regenBtn = e.target.closest('[data-regen]');
      const editBtn = e.target.closest('[data-edit]');
      if (regenBtn) {
        const idx = parseInt(regenBtn.dataset.regen);
        const history = storageManager.getChatHistory(currentChatId);
        if (idx > 0 && history[idx - 1]?.role === 'user') {
          const um = history[idx - 1].content; history.splice(idx, 1);
          storageManager.saveChatHistory(currentChatId, history); renderMessages(); streamAiReply(um);
        }
      }
      if (editBtn) {
        const idx = parseInt(editBtn.dataset.edit);
        const history = storageManager.getChatHistory(currentChatId);
        const old = history[idx]?.content || ''; const input = $('#chatInput');
        if (input) { input.value = old; input.focus(); }
        history.splice(idx, 1); if (history[idx]?.role === 'ai') history.splice(idx, 1);
        storageManager.saveChatHistory(currentChatId, history); renderMessages();
      }
    });
  }

  let knowledgeScope = 'system';  // "system" | "personal"

  DS.Chat = { init, sendMessage };

  // 检索范围切换
  document.querySelectorAll('.chat-scope-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const scope = btn.dataset.scope;
      if (scope === 'personal') {
        const uid = storageManager.getCurrentUserId();
        if (!uid) { Utils.showToast('请先登录', 'warning'); return; }
      }
      knowledgeScope = scope;
      document.querySelectorAll('.chat-scope-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
    });
  });
  // 立即初始化：因为 dashboard.js 在本脚本之前加载，
  // 其内部的 DS.Chat.init() 调用时 DS.Chat 尚未注册，需在此补调
  init();
})();
