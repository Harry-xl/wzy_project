/**
 * 聊天消息渲染模块
 * 处理Markdown渲染和代码高亮
 */

class MessageRenderer {
    constructor() {
        this.renderDebounceTimer = null;
        this.lastRenderedContent = '';
        this.initializeMarked();
    }

    /**
     * 初始化Marked.js配置
     */
    initializeMarked() {
        if (typeof marked !== 'undefined') {
            marked.setOptions({
                breaks: true,
                gfm: true,
                highlight: (code, language) => {
                    if (language && window.Prism && window.Prism.languages[language]) {
                        return Prism.highlight(code, Prism.languages[language], language);
                    }
                    return code;
                }
            });
        }
    }

    /**
     * 规范化（修复）Markdown 文本以提升兼容性
     * - 将 CRLF/CR 统一为 \n，避免在 Windows 环境下行分隔异常
     * - 为未加空格的标题与列表标记自动补空格（如 "##标题" -> "## 标题"；"-列表" -> "- 列表"；"1.条目" -> "1. 条目"）
     * - 保持原有内容不变，尽量不影响代码块内文本
     * @param {string} raw 原始文本
     * @returns {string} 规范化后的文本
     */
    normalizeMarkdown(raw) {
        if (!raw) return '';
        // 统一换行符为 \n
        let text = String(raw).replace(/\r\n?|\u000d\u000a?/g, '\n');

        // 为提升鲁棒性，避免在 fenced code block 内修改：
        // 简单策略：按 ``` 分割，只规范化非代码块片段，代码块片段保持原样
        const parts = text.split(/(^|\n)```.*?\n|\n```(?=\n|$)/g);
        // 上面 split 较难完全覆盖所有情况，采用更保守的基于状态的扫描
        let result = '';
        let inFence = false;
        let fenceLangOpened = false; // 仅用于跳过首行语言标记
        const lines = text.split('\n');
        for (let i = 0; i < lines.length; i++) {
            let line = lines[i];
            const fenceMatch = line.match(/^```/);
            if (fenceMatch) {
                // 进入/退出 围栏代码块
                inFence = !inFence;
                fenceLangOpened = inFence; // 进入后第一行可能是 ```lang
                result += (i > 0 ? '\n' : '') + line;
                continue;
            }
            if (inFence) {
                // 代码块内不做任何规范化
                result += (i > 0 ? '\n' : '') + line;
                continue;
            }

            // 宽字符变体归一化（仅在代码块外）
            // 将全角符号与破折号统一为 ASCII，提升 Markdown 兼容（如：＃ -> #，——— -> ---）
            line = line
                .replace(/＃/g, '#')
                .replace(/[－—–]/g, '-')
                .replace(/＋/g, '+')
                .replace(/＊/g, '*')
                .replace(/｀/g, '`');

            // 标题：在行首 # 序列后补空格（允许没有空格的情况）
            line = line.replace(/^(#{1,6})([^\s#])/g, (m, h, rest) => `${h} ${rest}`);
            // 无序列表：在行首 -,*,+ 后未跟空格时补空格（允许行前缩进）
            line = line.replace(/^(\s*[-*+])(\S)/g, (m, sym, ch) => `${sym} ${ch}`);
            // 有序列表：在行首 1. 2. 等后未跟空格时补空格（允许行前缩进）
            line = line.replace(/^(\s*\d+\.)(\S)/g, (m, num, ch) => `${num} ${ch}`);

            result += (i > 0 ? '\n' : '') + line;
        }
        return result;
    }

    /**
     * 渲染消息内容（支持Markdown和代码高亮）
     * - 优先使用 marked；若 CDN 加载失败，使用内置的简易 Markdown 解析，避免显示井号/星号的纯文本
     * @param {string} content - 原始消息内容
     * @returns {string} 渲染后的HTML
     */
    renderMessageContent(content) {
        if (!content) return '';

        try {
            // 预处理：提升对不规范 Markdown（缺少空格的标题/列表）的兼容性
            const normalized = this.normalizeMarkdown(content);
            // 安全检测，避免未定义的全局变量导致 ReferenceError
            const hasMarked = (typeof marked !== 'undefined');
            let html = hasMarked ? marked.parse(normalized) : this.simpleMarkdownParse(normalized);
            // 为代码块添加必要的CSS类
            html = this.processCodeBlocks(html);
            return html;
        } catch (error) {
            console.error('渲染消息内容失败:', error);
            // 兜底：至少做最基础的 Markdown 解析，尽量避免原样显示特殊符号
            try {
                const html = this.simpleMarkdownParse(content);
                return this.processCodeBlocks(html);
            } catch (_) {
                return this.escapeHtml(content);
            }
        }
    }

    /**
     * 简易Markdown解析（改进版，支持：标题、无序列表、行内样式、围栏代码块）
     * 说明：该解析器仅作为 CDN 加载失败时的兜底方案，能力有限
     * @param {string} content - 内容
     * @returns {string} HTML
     */
    simpleMarkdownParse(content) {
        // 先做轻量级规范化，避免 CRLF 与无空格标题/列表影响解析
        content = this.normalizeMarkdown(content);
        const lines = content.split('\n');
        let html = '';
        let inCode = false, inList = false;
        let codeBuffer = [], codeLang = '';
        let paragraphBuffer = [];

        const flushList = () => {
            if (inList) { html += '</ul>'; inList = false; }
        };
        const flushCode = () => {
            if (inCode && codeBuffer.length > 0) {
                const code = this.escapeHtml(codeBuffer.join('\n'));
                const langClass = codeLang ? ` language-${codeLang}` : '';
                html += `<pre><code class="${langClass}">${code}</code></pre>`;
                inCode = false; codeBuffer = []; codeLang = '';
            }
        };
        const flushParagraph = () => {
            if (paragraphBuffer.length > 0) {
                const text = paragraphBuffer.join(' ')
                    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                    .replace(/\*(.*?)\*/g, '<em>$1</em>')
                    .replace(/`(.*?)`/g, '<code>$1</code>');
                html += `<p>${text}</p>`;
                paragraphBuffer = [];
            }
        };

        for (let raw of lines) {
            const line = raw.trim();
            
            // 分隔线 (连续3个或以上短线)
            if (line.match(/^-{3,}$/)) {
                flushParagraph();
                flushList();
                html += '<hr>';
                continue;
            }
            
            // 围栏代码块 ```lang
            const fenceMatch = line.match(/^```\s*(\w+)?\s*$/);
            if (fenceMatch) {
                flushParagraph();
                if (!inCode) {
                    // 开始代码块
                    flushList();
                    inCode = true;
                    codeLang = fenceMatch[1] || '';
                    codeBuffer = [];
                } else {
                    // 结束代码块
                    flushCode();
                }
                continue;
            }
            if (inCode) {
                codeBuffer.push(raw); // 保持原始缩进
                continue;
            }

            // 标题 #, ##, ... ###### (允许井号后无空格)
            const hMatch = line.match(/^(#{1,6})\s*(.*)$/);
            if (hMatch && hMatch[2].trim()) {
                flushParagraph();
                flushList();
                const level = hMatch[1].length;
                const text = this.escapeHtml(hMatch[2].trim());
                html += `<h${level}>${text}</h${level}>`;
                continue;
            }

            // 无序列表 - 允许 * + - 开头
            const liMatch = line.match(/^\s*([*+-])\s+(.+)$/);
            if (liMatch) {
                flushParagraph();
                if (!inList) { html += '<ul>'; inList = true; }
                const text = this.escapeHtml(liMatch[2])
                    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                    .replace(/\*(.*?)\*/g, '<em>$1</em>')
                    .replace(/`(.*?)`/g, '<code>$1</code>');
                html += `<li>${text}</li>`;
                continue;
            } else {
                flushList();
            }

            // 空行处理 - 结束当前段落
            if (line.length === 0) {
                flushParagraph();
                continue;
            }

            // 普通文本 - 累积到段落缓冲区
            const cleanText = this.escapeHtml(line);
            paragraphBuffer.push(cleanText);
        }
        
        // 清理剩余内容
        flushParagraph();
        flushCode();
        flushList();
        return html;
    }

    /**
     * 处理代码块，添加必要的CSS类
     * @param {string} html - HTML内容
     * @returns {string} 处理后的HTML
     */
    processCodeBlocks(html) {
        // 为有语言标识的代码块添加line-numbers类
        html = html.replace(/<pre><code class=\"language-(\w+)\">/g, (match, lang) => {
            return `<pre class="line-numbers language-${lang}"><code class="language-${lang}">`;
        });
        // 为无语言标识的代码块添加默认类
        html = html.replace(/<pre><code>/g,
            '<pre class="line-numbers language-none"><code class="language-none">');
        return html;
    }

    /**
     * 转义HTML字符
     * @param {string} text - 文本内容
     * @returns {string} 转义后的文本
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text == null ? '' : String(text);
        return div.innerHTML;
    }

    /**
     * 智能实时渲染（支持流式更新）
     * @param {HTMLElement} element - 目标元素
     * @param {string} fullContent - 完整内容
     */
    smartRealTimeRender(element, fullContent) {
        if (!element) return;
        element.innerHTML = this.renderMessageContent(fullContent);
        this.addLineNumbers(element, true);
    }

    /**
     * 为代码块添加行号
     * @param {HTMLElement} element - 目标元素
     */
    addLineNumbers(element) {
        const preElements = element.querySelectorAll('pre.line-numbers');
        preElements.forEach(pre => {
            if (pre.querySelector('.line-numbers-rows')) return;
            const code = pre.querySelector('code');
            if (!code) return;
            const lines = code.textContent.split('\n');
            const lineCount = lines.length;
            const lineNumbersRows = document.createElement('span');
            lineNumbersRows.className = 'line-numbers-rows';
            lineNumbersRows.setAttribute('aria-hidden', 'true');
            for (let i = 0; i < lineCount; i++) {
                const span = document.createElement('span');
                lineNumbersRows.appendChild(span);
            }
            pre.appendChild(lineNumbersRows);
        });
        // 新增：渲染后触发 Prism 语法高亮（若可用）
        try {
            if (window.Prism && typeof Prism.highlightAllUnder === 'function') {
                Prism.highlightAllUnder(element);
            }
        } catch (error) {
            console.error('代码高亮应用失败:', error);
        }
    }

    /**
     * 清除防抖定时器
     */
    clearRenderTimer() {
        if (this.renderDebounceTimer) {
            clearTimeout(this.renderDebounceTimer);
            this.renderDebounceTimer = null;
        }
    }

    /**
     * 最终渲染（用于流式传输完成后）
     * @param {HTMLElement} element - 目标元素
     * @param {string} content - 完整内容
     */
    finalRender(element, content) {
        this.clearRenderTimer();
        if (element && content) {
            element.innerHTML = this.renderMessageContent(content);
            this.addLineNumbers(element, false);
        }
    }

    /**
     * 创建消息元素（优化：带操作按钮）
     * @param {Object} message - 消息对象
     * @param {Array} messages - 全部消息（用于判断相邻关系）
     * @param {number} idx - 当前消息索引
     * @returns {HTMLElement} 消息DOM元素
     */
    createMessageElement(message, messages = [], idx = 0, showActions = true) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${message.role}`;
        if (message.role === 'ai') {
            const avatar = document.createElement('div');
            avatar.className = 'ai-avatar';
            avatar.innerHTML = '<img src="assets/girl.png" alt="AI" style="width:44px;height:44px;border-radius:50%;object-fit:cover;">';
            messageDiv.appendChild(avatar);
        }
        if (message.role === 'user') {
            const userAvatar = document.createElement('div');
            userAvatar.className = 'user-avatar';
            let avatarSrc = localStorage.getItem('userAvatar') || 'assets/user-avatar.svg';
            userAvatar.innerHTML = `<img src="${avatarSrc}" alt="用户头像" style="width:44px;height:44px;border-radius:50%;object-fit:cover;">`;
            messageDiv.appendChild(userAvatar);
        }
        const bubble = document.createElement('div');
        bubble.className = `bubble ${message.role}`;
        bubble.innerHTML = this.renderMessageContent(message.content);
        messageDiv.appendChild(bubble);
        this.addLineNumbers(bubble);

        // RAG 来源引用卡片
        if (message.role === 'ai' && message.sources && message.sources.length > 0) {
            const sourcesCard = document.createElement('div');
            sourcesCard.className = 'sources-card';
            let sourcesHtml = '<div class="sources-title"><i class="ri-book-open-line"></i> 参考来源</div>';
            message.sources.forEach(s => {
                const scorePct = s.score ? ` <span class="source-score">相关性 ${Math.round(s.score * 100)}%</span>` : '';
                const src = (typeof Utils !== 'undefined' && Utils.escapeHtml)
                    ? Utils.escapeHtml(s.source || '')
                    : (s.source || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
                const title = (typeof Utils !== 'undefined' && Utils.escapeHtml)
                    ? Utils.escapeHtml(s.title || '')
                    : (s.title || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
                const page = s.source_page || '';
                sourcesHtml += `<div class="source-item"><span class="source-index">${s.index}</span> ${src} · ${title}${page ? ' · ' + (typeof Utils !== 'undefined' && Utils.escapeHtml ? Utils.escapeHtml(page) : page) : ''}${scorePct}</div>`;
            });
            sourcesCard.innerHTML = sourcesHtml;
            bubble.appendChild(sourcesCard);
        }

        // 操作按钮区域，悬停时显示
        if (showActions) {
            const actions = document.createElement('div');
            actions.className = 'bubble-actions';
            // DeepSeek风格：AI左下，用户右下，按钮组另起一行
            if (message.role === 'user') {
                actions.style.left = 'auto';
                actions.style.right = '6px';
                actions.style.bottom = '-4px';
                actions.style.top = 'auto';
                actions.style.justifyContent = 'flex-end';
            } else if (message.role === 'ai') {
                actions.style.left = '6px';
                actions.style.right = 'auto';
                actions.style.bottom = '-4px';
                actions.style.top = 'auto';
                actions.style.justifyContent = 'flex-start';
            }
            actions.style.position = 'absolute';
            actions.style.display = 'flex';
            actions.style.alignItems = 'center';
            actions.style.gap = '8px';
            actions.style.fontSize = '18px';
            actions.style.opacity = '0';
            actions.style.background = 'rgba(30,30,30,0.92)';
            actions.style.borderRadius = '8px';
            actions.style.boxShadow = '0 2px 8px rgba(0,0,0,0.10)';
            actions.style.padding = '2px 8px';
            actions.style.pointerEvents = 'none';
            actions.style.transition = 'opacity 0.2s';
            actions.style.userSelect = 'none';
            // 悬停/触控时渐显
            bubble.addEventListener('mouseenter', () => {
                actions.style.opacity = '1';
                actions.style.pointerEvents = 'auto';
            });
            bubble.addEventListener('mouseleave', () => {
                actions.style.opacity = '0';
                actions.style.pointerEvents = 'none';
            });
            bubble.addEventListener('touchstart', () => {
                actions.style.opacity = '1';
                actions.style.pointerEvents = 'auto';
            });
            bubble.addEventListener('touchend', () => {
                setTimeout(() => {
                    actions.style.opacity = '0';
                    actions.style.pointerEvents = 'none';
                }, 600);
            });

            // 复制按钮
            const copyBtn = document.createElement('i');
            copyBtn.className = 'ri-file-copy-line action-btn';
            copyBtn.title = '复制';
            copyBtn.style.cursor = 'pointer';
            copyBtn.onclick = () => {
                navigator.clipboard.writeText(message.content);
                Utils.showToast('已复制到剪贴板');
            };
            actions.appendChild(copyBtn);

            if (message.role === 'ai') {
                // 重新生成
                const regenBtn = document.createElement('i');
                regenBtn.className = 'ri-refresh-line action-btn';
                regenBtn.title = '重新生成';
                regenBtn.style.cursor = 'pointer';
                regenBtn.onclick = () => {
                    if (typeof window.regenerateAiReply === 'function') {
                        window.regenerateAiReply(idx);
                    }
                };
                actions.appendChild(regenBtn);
                // 点赞
                const likeBtn = document.createElement('i');
                likeBtn.className = 'ri-thumb-up-line action-btn';
                likeBtn.title = '点赞';
                likeBtn.style.cursor = 'pointer';
                likeBtn.onclick = () => {
                    likeBtn.classList.toggle('active');
                    dislikeBtn.classList.remove('active');
                    Utils.showToast(likeBtn.classList.contains('active') ? '已点赞' : '已取消点赞');
                    if (likeBtn.classList.contains('active')) {
                        if (typeof window.sendAiFeedback === 'function') {
                            window.sendAiFeedback('很好');
                        }
                    }
                };
                actions.appendChild(likeBtn);
                // 踩
                const dislikeBtn = document.createElement('i');
                dislikeBtn.className = 'ri-thumb-down-line action-btn';
                dislikeBtn.title = '踩';
                dislikeBtn.style.cursor = 'pointer';
                dislikeBtn.onclick = () => {
                    dislikeBtn.classList.toggle('active');
                    likeBtn.classList.remove('active');
                    Utils.showToast(dislikeBtn.classList.contains('active') ? '已点踩' : '已取消点踩');
                    if (dislikeBtn.classList.contains('active')) {
                        if (typeof window.sendAiFeedback === 'function') {
                            window.sendAiFeedback('不好');
                        }
                    }
                };
                actions.appendChild(dislikeBtn);
            }
            if (message.role === 'user') {
                // 只允许最新一条用户消息有修改按钮
                const isLatestUserMsg = (() => {
                    // 找到所有用户消息的索引
                    const userMsgIndexes = messages
                        .map((msg, i) => msg.role === 'user' ? i : -1)
                        .filter(i => i !== -1);
                    return userMsgIndexes.length > 0 && idx === userMsgIndexes[userMsgIndexes.length - 1];
                })();
                if (isLatestUserMsg) {
                    const editBtn = document.createElement('i');
                    editBtn.className = 'ri-edit-2-line action-btn';
                    editBtn.title = '修改';
                    editBtn.style.cursor = 'pointer';
                    editBtn.onclick = () => {
                        if (typeof window.editUserMessage === 'function') {
                            window.editUserMessage(idx);
                        }
                    };
                    actions.appendChild(editBtn);
                }
            }
            bubble.appendChild(actions);
        }
        return messageDiv;
    }

    /**
     * 创建日期分隔符元素
     * @param {string} date - 日期字符串
     * @returns {HTMLElement} 日期分隔符DOM元素
     */
    createDateSeparator(date) {
        const dateDiv = document.createElement('div');
        dateDiv.className = 'chat-date';
        dateDiv.textContent = date;
        return dateDiv;
    }

    /**
     * 批量渲染消息列表（兼容聊天页面）
     * - 保持与 chat.js 的交互契约：支持 streamingIdx 高亮/定位
     * @param {Array} messages - 消息列表
     * @param {HTMLElement} container - 容器元素
     * @param {number} streamingIdx - 正在流式更新的消息索引（可选）
     */
    renderMessageList(messages, container, streamingIdx = -1) {
        if (!container) return;
        container.innerHTML = '';
        const groupByDate = {};
        messages.forEach(msg => {
            const date = (typeof Utils !== 'undefined' && Utils.formatDate)
                ? Utils.formatDate(msg.time)
                : new Date(msg.time || Date.now()).toLocaleDateString();
            if (!groupByDate[date]) groupByDate[date] = [];
            groupByDate[date].push(msg);
        });
        Object.keys(groupByDate)
            .sort()
            .forEach(date => {
                container.appendChild(this.createDateSeparator(date));
                groupByDate[date].forEach((msg, idx) => {
                    // 展示操作按钮：保持与旧行为一致（如复制/重试等，若存在）
                    const showActions = true;
                    container.appendChild(this.createMessageElement(msg, groupByDate[date], idx, showActions));
                });
            });
    }
}

// 创建全局消息渲染器实例（供 chat.js 等直接使用）
if (typeof window !== 'undefined') {
    window.messageRenderer = window.messageRenderer || new MessageRenderer();
}

// CommonJS 导出（若被打包工具引用）
if (typeof module !== 'undefined' && module.exports) {
    module.exports = MessageRenderer;
}
