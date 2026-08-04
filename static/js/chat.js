/**
 * 聊天页面主逻辑模块
 * 负责页面初始化、事件绑定、消息流式处理等
 * Updated: 2025-01-13
 */

// 依赖：api.js, storage.js, renderer.js, utils.js

document.addEventListener('DOMContentLoaded', function() {
    // 登录校验
    if (!storageManager.isLoggedIn()) {
        window.location.href = 'login.html';
        return;
    }

    // DOM元素
    const chatBody = document.getElementById('chatBody');
    const chatForm = document.getElementById('chatForm');
    const chatInput = document.getElementById('chatInput');
    const stopBtn = document.getElementById('stopBtn');
    const chatHistoryList = document.getElementById('chatHistoryList');
    const chatWelcome = document.getElementById('chatWelcome');
    const chatTitle = document.getElementById('chatTitle');
    const newChatBtn = document.getElementById('newChatBtn');
    const sidebar = document.getElementById('chatSidebar');
    const sidebarHoverArea = document.getElementById('sidebarHoverArea');
    


    // 聊天状态
    let aiControllers = {}; // chatId: AbortController
    let aiStreamCache = {}; // chatId: {content: string, streamingIdx: number, sources: Array|null}
    let currentChatId = storageManager.getCurrentChatId();
    let chatList = storageManager.getChatList();

    // 页面加载后自动新建或选中对话并显示历史
    if (!chatList || chatList.length === 0) {
        // 没有历史对话，自动新建一个
        const newChat = storageManager.createNewChat();
        chatList = storageManager.getChatList();
        currentChatId = newChat.id;
        storageManager.setCurrentChatId(currentChatId);
    } else if (!currentChatId || !chatList.find(c => c.id === currentChatId)) {
        // 有历史但未选中，自动选中第一个
        currentChatId = chatList[0].id;
        storageManager.setCurrentChatId(currentChatId);
    }
    renderChatHistory();
    renderHistory(true);

    // 渲染对话历史
    function renderChatHistory() {
        chatHistoryList.innerHTML = '';
        if (chatList.length === 0) {
            const empty = document.createElement('div');
            empty.style.cssText = 'color: #aaa; text-align: center; margin-top: 30px;';
            empty.textContent = '暂无对话';
            chatHistoryList.appendChild(empty);
            return;
        }
        // 按日期分组
        const groupByDate = {};
        chatList.forEach(chat => {
            const date = Utils.formatDate(chat.time);
            if (!groupByDate[date]) groupByDate[date] = [];
            groupByDate[date].push(chat);
        });
        Object.keys(groupByDate).sort().reverse().forEach(date => {
            const dateDiv = document.createElement('div');
            dateDiv.className = 'chat-date';
            dateDiv.textContent = date;
            chatHistoryList.appendChild(dateDiv);
            groupByDate[date].forEach(chat => {
                const item = createChatHistoryItem(chat);
                chatHistoryList.appendChild(item);
            });
        });
    }

    function createChatHistoryItem(chat) {
        const item = document.createElement('div');
        item.className = 'chat-history-item' + (chat.id === currentChatId ? ' active' : '');
        const titleSpan = document.createElement('span');
        titleSpan.textContent = chat.title || '新对话';
        const delBtn = document.createElement('button');
        delBtn.textContent = '×';
        delBtn.className = 'del-chat-btn';
        delBtn.title = '删除对话';
        delBtn.onclick = function(e) {
            e.stopPropagation();
            if (confirm('确定要删除该对话吗？')) {
                storageManager.deleteChat(chat.id);
                chatList = storageManager.getChatList();
                if (currentChatId === chat.id) {
                    currentChatId = chatList.length > 0 ? chatList[0].id : null;
                    storageManager.setCurrentChatId(currentChatId);
                }
                renderChatHistory();
                renderHistory(true);
            }
        };
        item.appendChild(titleSpan);
        const delWrap = document.createElement('span');
        delWrap.className = 'btn-outline';
        delWrap.appendChild(delBtn);
        item.appendChild(delWrap);
        item.onclick = function() {
            currentChatId = chat.id;
            storageManager.setCurrentChatId(currentChatId);
            // 重置个性化设置标志，确保切换对话后会发送个性化信息
            window._personalizePromptSent = false;
            renderChatHistory();
            renderHistory();
        };
        return item;
    }

    // 新建对话
    newChatBtn.onclick = function() {
        // 检查是否已有未提问的新对话
        const hasEmpty = chatList.find(c => {
            const his = storageManager.getChatHistory(c.id);
            return (c.title === '新对话' || !c.title) && his.length === 0;
        });
        if (hasEmpty) {
            currentChatId = hasEmpty.id;
            storageManager.setCurrentChatId(currentChatId);
            // 重置个性化设置标志，确保新对话会发送个性化信息
            window._personalizePromptSent = false;
            // 重置提示词为默认值
            apiClient.setSystemPrompt(storageManager.currentUser, currentChatId, null)
                .catch(error => console.error('重置系统提示词错误:', error));
            renderChatHistory();
            renderHistory(true);
            return;
        }
        // 创建新对话
        const newChat = storageManager.createNewChat();
        chatList = storageManager.getChatList();
        currentChatId = newChat.id;
        storageManager.setCurrentChatId(currentChatId);
        // 重置个性化设置标志，确保新对话会发送个性化信息
        window._personalizePromptSent = false;
        // 设置默认系统提示词
        apiClient.setSystemPrompt(storageManager.currentUser, currentChatId, null)
            .catch(error => console.error('设置默认系统提示词错误:', error));
        renderChatHistory();
        renderHistory(true);
    };

    // 渲染欢迎语
    function getWelcome() {
        const hour = new Date().getHours();
        let greet = '你好';
        if (hour < 11) greet = '早上好';
        else if (hour < 14) greet = '中午好';
        else if (hour < 18) greet = '下午好';
        else greet = '晚上好';
        return greet + '，' + storageManager.getCurrentUserName() + '！';
    }
    chatWelcome.textContent = getWelcome();

    // 渲染聊天历史
    function renderHistory(scrollToBottom) {
        // 获取当前对话历史
        const history = currentChatId ? storageManager.getChatHistory(currentChatId) : [];
        chatBody.innerHTML = '';
        if (!currentChatId) {
            chatWelcome.style.display = '';
            chatTitle.textContent = '';
            updateInputPosition();
            return;
        }
        chatWelcome.style.display = history.length === 0 ? '' : 'none';
        const chatObj = chatList.find(c => c.id === currentChatId);
        chatTitle.textContent = chatObj ? chatObj.title : '';
        // 检查是否有流式缓存
        if (aiStreamCache[currentChatId]) {
            // 渲染带流式内容的历史
            const hisCopy = history.slice();
            const {content, streamingIdx} = aiStreamCache[currentChatId];
            if (typeof streamingIdx === 'number' && hisCopy[streamingIdx]) {
                hisCopy[streamingIdx] = {...hisCopy[streamingIdx], content};
                messageRenderer.renderMessageList(hisCopy, chatBody, streamingIdx);
            } else {
                messageRenderer.renderMessageList(history, chatBody);
            }
        } else {
            messageRenderer.renderMessageList(history, chatBody);
        }
        if (scrollToBottom) {
            chatBody.scrollTop = chatBody.scrollHeight;
        }
        updateInputPosition();
    }

    // 输入框状态管理
    function updateInputPosition() {
        const history = currentChatId ? storageManager.getChatHistory(currentChatId) : [];
        const hasMessages = history.length > 0;
        
        if (hasMessages) {
            // 有消息时，输入框在底部
            chatForm.classList.remove('centered');
        } else {
            // 无消息时，输入框居中
            chatForm.classList.add('centered');
        }
    }
    
    // 暴露给全局，以便侧边栏事件调用
    window.updateInputPosition = updateInputPosition;

    // 修改AI流式渲染：只在当前激活对话渲染流式内容
    function streamAiReply(userMsg) {
        // 先检查是否需要发送个性化设置prompt
        if (!window._personalizePromptSent) {
            const info = JSON.parse(localStorage.getItem('personalizeInfo')||'{}');
            let prefix = '';
            if(info.aiName && info.aiName.trim()) prefix += `请称呼我为${info.aiName}。`;
            if(info.identity && info.identity.trim()) prefix += `我的身份是${info.identity}。`;
            if(info.hobbies && info.hobbies.trim()) prefix += `我的兴趣爱好：${info.hobbies}。`;
            if(prefix) {
                // 只发给AI，不显示在聊天气泡
                apiClient.chatStream(prefix, storageManager.currentUser, currentChatId, null, aiControllers[currentChatId]?.signal);
            }
            window._personalizePromptSent = true;
        }
        const history = storageManager.getChatHistory(currentChatId);
        if (history.length > 0 && history[history.length - 1].role === 'ai' && !history[history.length - 1].content) {
            history.pop();
        }
        const aiMsgPlaceholder = {role: 'ai', content: '', time: Date.now()};
        history.push(aiMsgPlaceholder);
        storageManager.saveChatHistory(currentChatId, history);
        // 记录流式缓存
        aiStreamCache[currentChatId] = {content: '', streamingIdx: history.length - 1};
        renderHistory(true);
        const aiBubble = document.querySelector('.message.ai:last-child .bubble');
        if (!aiBubble) return;
        if (!aiControllers) aiControllers = {};
        aiControllers[currentChatId] = new AbortController();
        stopBtn.style.display = '';
        
        // 不传入系统提示词，使用后端保存的设置
        apiClient.chatStream(userMsg, storageManager.currentUser, currentChatId, null, aiControllers[currentChatId].signal)
            .then(response => {
                if (!response.ok) {
                    handleAiError(aiBubble, '抱歉，AI服务当前不可用。');
                    delete aiStreamCache[currentChatId];
                    return;
                }
                const reader = response.body.getReader();
                const decoder = new TextDecoder('utf-8');
                let fullReply = '';
                function readStream() {
                    reader.read().then(({ done, value }) => {
                        if (done) {
                            finishAiReply(fullReply);
                            delete aiStreamCache[currentChatId];
                            return;
                        }
                        const chunk = decoder.decode(value, { stream: true });
                        const lines = chunk.split('\n\n');
                        lines.forEach(line => {
                            if (line.startsWith('data: ')) {
                                try {
                                    const data = JSON.parse(line.substring(6));
                                    if (data.reply) {
                                        fullReply += data.reply;
                                        aiMsgPlaceholder.content = fullReply;
                                        // 更新流式缓存
                                        aiStreamCache[currentChatId] = {content: fullReply, streamingIdx: history.length - 1};
                                        // 只渲染当前对话
                                        if (currentChatId === storageManager.getCurrentChatId()) {
                                            renderHistory(true);
                                        }
                                    }
                                    // RAG 来源引用提取
                                    if (data.done && data.sources) {
                                        aiMsgPlaceholder.sources = data.sources;
                                        if (aiStreamCache[currentChatId]) {
                                            aiStreamCache[currentChatId].sources = data.sources;
                                        }
                                    }
                                } catch (e) {
                                    console.error('解析流数据出错:', e);
                                }
                            }
                        });
                        readStream();
                    }).catch(err => {
                        if (err.name === 'AbortError') {
                            // AbortError通常由stopBtn.onclick处理，这里不需要额外处理
                            // 因为停止按钮已经保存了内容并更新了显示
                        } else {
                            handleAiError(aiBubble, '抱歉，AI服务当前不可用。');
                            delete aiStreamCache[currentChatId];
                        }
                    });
                }
                readStream();
            })
            .catch(error => {
                console.error('流式传输错误:', error);
                handleAiError(aiBubble, '抱歉，AI服务当前不可用。');
                delete aiStreamCache[currentChatId];
            });
    }

    function handleAiError(aiBubble, errorMsg) {
        stopBtn.style.display = 'none';
        if (aiControllers[currentChatId]) aiControllers[currentChatId] = null;
        aiBubble.textContent = errorMsg;
    }

    function finishAiReply(fullReply) {
        stopBtn.style.display = 'none';
        if (aiControllers[currentChatId]) aiControllers[currentChatId] = null;
        messageRenderer.clearRenderTimer();
        let finalHis = storageManager.getChatHistory(currentChatId);
        const lastMsg = finalHis[finalHis.length - 1];
        if (lastMsg && lastMsg.role === 'ai') {
            lastMsg.content = fullReply;
            // 保留 RAG 来源引用
            const cache = aiStreamCache[currentChatId];
            if (cache && cache.sources) {
                lastMsg.sources = cache.sources;
            }
            storageManager.saveChatHistory(currentChatId, finalHis);
        }
        delete aiStreamCache[currentChatId];
        if (currentChatId === storageManager.getCurrentChatId()) {
            messageRenderer.renderMessageList(finalHis, chatBody, -1);
            chatBody.scrollTop = chatBody.scrollHeight;
        }
    }
    stopBtn.onclick = function() {
        if (aiControllers[currentChatId]) {
            // 在停止前保存已生成的内容
            const cache = aiStreamCache[currentChatId];
            if (cache && cache.content) {
                let finalHis = storageManager.getChatHistory(currentChatId);
                const lastMsg = finalHis[finalHis.length - 1];
                if (lastMsg && lastMsg.role === 'ai') {
                    lastMsg.content = cache.content + '\n\n[已手动停止生成]';
                    // 保留 RAG 来源引用
                    if (cache.sources) {
                        lastMsg.sources = cache.sources;
                    }
                    storageManager.saveChatHistory(currentChatId, finalHis);
                }
            }

            aiControllers[currentChatId].abort();
            aiControllers[currentChatId] = null;
            this.style.display = 'none';

            // 清理流式缓存
            delete aiStreamCache[currentChatId];

            // 重新渲染消息列表以显示保存的内容
            if (currentChatId === storageManager.getCurrentChatId()) {
                const history = storageManager.getChatHistory(currentChatId);
                messageRenderer.renderMessageList(history, chatBody, -1);
                chatBody.scrollTop = chatBody.scrollHeight;
            }
        }
    };

    chatForm.onsubmit = function(e) {
        e.preventDefault();
        const userMsg = chatInput.value.trim();
        if (!userMsg) return;
        if (!currentChatId) {
            const newChat = storageManager.createNewChat();
            chatList = storageManager.getChatList();
            currentChatId = newChat.id;
            storageManager.setCurrentChatId(currentChatId);
            renderChatHistory();
        }
        const history = storageManager.getChatHistory(currentChatId);
        history.push({role: 'user', content: userMsg, time: Date.now()});
        storageManager.saveChatHistory(currentChatId, history);
        renderHistory(true);
        chatInput.value = '';
        streamAiReply(userMsg);
        updateChatTitle(userMsg);
    };

    function updateChatTitle(userMsg) {
        const chatObj = chatList.find(c => c.id === currentChatId);
        if (chatObj && (chatObj.title === '新对话' || !chatObj.title)) {
            chatObj.title = userMsg.length > 10 ? userMsg.slice(0,10)+'...' : userMsg;
            storageManager.saveChatList(chatList);
            renderChatHistory();
        }
    }
    chatInput.placeholder = '星伴，你的AI智能陪伴，快来和我聊天吧！';

    // Prism自动加载器配置
    if (window.Prism && window.Prism.plugins && window.Prism.plugins.autoloader) {
        window.Prism.plugins.autoloader.languages_path = 'https://cdn.jsdelivr.net/npm/prismjs@1.29.0/components/';
    }

    // AI重新生成功能
    window.regenerateAiReply = function(aiIdx) {
        const history = storageManager.getChatHistory(currentChatId);
        // 找到前一个用户消息
        if (aiIdx > 0 && history[aiIdx - 1].role === 'user') {
            const userMsg = history[aiIdx - 1].content;
            // 删除当前AI回复
            history.splice(aiIdx, 1);
            storageManager.saveChatHistory(currentChatId, history);
            renderHistory(true);
            streamAiReply(userMsg);
        } else {
            Utils.showToast('无法重新生成');
        }
    };
    // 用户消息修改功能
    window.editUserMessage = function(userIdx) {
        const history = storageManager.getChatHistory(currentChatId);
        const userMsg = history[userIdx].content;
        // 只允许修改与AI相邻的用户消息
        if (userIdx < history.length - 1 && history[userIdx + 1].role === 'ai') {
            chatInput.value = userMsg;
            chatInput.focus();
            // 修改提交时替换原内容并重新生成AI
            chatForm.onsubmit = function(e) {
                e.preventDefault();
                const newMsg = chatInput.value.trim();
                if (!newMsg) return;
                history[userIdx].content = newMsg;
                // 删除后面AI回复
                history.splice(userIdx + 1, 1);
                storageManager.saveChatHistory(currentChatId, history);
                renderHistory(true);
                chatInput.value = '';
                streamAiReply(newMsg);
                updateChatTitle(newMsg);
                // 恢复默认提交
                chatForm.onsubmit = defaultSubmit;
            };
        } else {
            Utils.showToast('仅可修改与AI相邻的用户消息');
        }
    };
    // 备份默认提交
    const defaultSubmit = chatForm.onsubmit;

    // 点赞/踩后显示简短悬浮提示
    window.sendAiFeedback = function(feedback) {
        if (!currentChatId) return;
        // 显示"已收到您的反馈"的悬浮提示，1秒后自动消失
        Utils.showToast('已收到您的反馈', 1000);
        
        // 可选：记录反馈但不显示在对话中
        // 如果需要在后台记录反馈但不显示在对话历史中，可以使用下面的代码：
        // const feedbackData = {
        //     chatId: currentChatId,
        //     feedback: feedback,
        //     timestamp: Date.now()
        // };
        // localStorage.setItem('feedback_' + Date.now(), JSON.stringify(feedbackData));
    };

    // 头像上传事件
    const userAvatarInput = document.getElementById('userAvatarInput');
    if (userAvatarInput) {
        userAvatarInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = function(evt) {
                if (evt.target.result) {
                    // 存储base64到localStorage
                    localStorage.setItem('userAvatar', evt.target.result);
                    // 刷新页面以应用新头像
                    window.location.reload();
                }
            };
            reader.readAsDataURL(file);
        });
    }

    // 聊天页头像上传与预览
    const chatUserAvatar = document.getElementById('chatUserAvatar');
    if (chatUserAvatar) {
        const saved = localStorage.getItem('userAvatar');
        if (saved) chatUserAvatar.src = saved;
    }

    // 新按钮事件处理 - 已删除思考模式和模型选择

    // 初始化输入框位置
    updateInputPosition();

    // 智能侧边栏悬停展开/收起（延迟初始化）
    setTimeout(function() {
        const sidebarElement = document.getElementById('chatSidebar');
        const hoverAreaElement = document.getElementById('sidebarHoverArea');
        
        function expandSidebar() {
            if (sidebarElement) {
                sidebarElement.classList.add('expanded');
            }
        }
        
        function collapseSidebar() {
            if (sidebarElement) {
                sidebarElement.classList.remove('expanded');
            }
        }
        
        if (hoverAreaElement) {
            hoverAreaElement.addEventListener('mouseenter', expandSidebar);
        }
        if (sidebarElement) {
            sidebarElement.addEventListener('mouseenter', expandSidebar);
            sidebarElement.addEventListener('mouseleave', collapseSidebar);
            // 页面加载默认收起
            collapseSidebar();
        }
    }, 100);
});
