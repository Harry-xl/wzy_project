/**
 * StarPal 我的资料库 — 主模块
 * 文件上传、文档列表、进度追踪
 */
'use strict';

(function () {
  const DS = window.__DS;
  if (!DS) return;

  DS.Library = {
    _initialized: false,
    _uploading: false,

    init() {
      if (this._initialized) return;
      this._initialized = true;

      const uploadZone = DS.$('#libraryUploadZone');
      const fileInput = DS.$('#libraryFileInput');
      const selectBtn = DS.$('#librarySelectFileBtn');
      const nodeModal = DS.$('#libraryNodeModal');
      const nodeModalClose = DS.$('#libraryNodeModalClose');

      // 点击选择文件
      selectBtn?.addEventListener('click', () => fileInput?.click());
      uploadZone?.addEventListener('click', (e) => {
        if (e.target !== selectBtn && !selectBtn?.contains(e.target)) fileInput?.click();
      });
      fileInput?.addEventListener('change', () => {
        if (fileInput.files.length) this._handleFile(fileInput.files[0]);
      });

      // 拖拽上传
      uploadZone?.addEventListener('dragover', (e) => { e.preventDefault(); uploadZone.classList.add('drag-over'); });
      uploadZone?.addEventListener('dragleave', () => uploadZone.classList.remove('drag-over'));
      uploadZone?.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('drag-over');
        const file = e.dataTransfer?.files?.[0];
        if (file) this._handleFile(file);
      });

      // 模态框关闭
      nodeModalClose?.addEventListener('click', () => { if (nodeModal) nodeModal.style.display = 'none'; });
      nodeModal?.addEventListener('click', (e) => { if (e.target === nodeModal) nodeModal.style.display = 'none'; });

      // 知识清单 Tab 切换
      document.querySelectorAll('.library-tab').forEach(tab => {
        tab.addEventListener('click', () => {
          const tabName = tab.dataset.tab;
          document.querySelectorAll('.library-tab').forEach(t => t.classList.remove('active'));
          tab.classList.add('active');
          DS.$('#libraryTabByTopic').style.display = tabName === 'by-topic' ? 'block' : 'none';
          DS.$('#libraryTabByDoc').style.display = tabName === 'by-doc' ? 'block' : 'none';
          if (tabName === 'by-doc') { if (DS.LibraryKnowledge) DS.LibraryKnowledge.loadDocView(); }
        });
      });

      // 推荐补充按钮
      DS.$('#libraryHighlightBtn')?.addEventListener('click', () => {
        if (DS.LibraryGraph) DS.LibraryGraph.highlightUncovered();
      });

      // 点击其他地方关闭导出下拉
      document.addEventListener('click', (e) => {
        if (!e.target.closest('.library-doc-export-wrap')) {
          document.querySelectorAll('.library-export-dropdown.open').forEach(d => d.classList.remove('open'));
        }
      });

      // 加载文档列表
      this.loadDocuments();
    },

    async _handleFile(file) {
      const maxMB = 200;
      if (file.size > maxMB * 1024 * 1024) {
        Utils.showToast(`文件过大 (${(file.size/1024/1024).toFixed(1)}MB)，请上传不超过 ${maxMB}MB 的文件`, 'error');
        return;
      }
      const ext = file.name.split('.').pop()?.toLowerCase();
      if (!['pdf', 'docx'].includes(ext || '')) {
        Utils.showToast('不支持的文件格式，仅支持 PDF 和 Word (.docx)', 'error');
        return;
      }

      if (this._uploading) { Utils.showToast('已有文件在上传中，请等待完成', 'warning'); return; }
      this._uploading = true;

      const docType = DS.$('#libraryDocType')?.value || 'other';
      const formData = new FormData();
      formData.append('file', file);
      formData.append('user_id', String(DS.userId || 0));
      formData.append('doc_type', docType);
      formData.append('title', file.name);

      try {
        const resp = await fetch('http://127.0.0.1:3001/api/library/upload', {
          method: 'POST', body: formData,
        });
        const data = await resp.json();
        if (data.success) {
          Utils.showToast('文件已上传，正在后台处理...', 'success');
          this._watchProgress(data.task_id);
        } else {
          Utils.showToast(data.message || '上传失败', 'error');
        }
      } catch (err) {
        Utils.showToast('网络错误，请重试', 'error');
      }
      this._uploading = false;
    },

    _watchProgress(taskId) {
      const progressEl = DS.$('#libraryProgress');
      const stepEl = DS.$('#libraryProgressStep');
      const pctEl = DS.$('#libraryProgressPct');
      const fillEl = DS.$('#libraryProgressFill');

      if (progressEl) progressEl.style.display = 'block';
      if (stepEl) stepEl.textContent = '等待处理...';
      if (pctEl) pctEl.textContent = '0%';
      if (fillEl) fillEl.style.width = '2%';  // 微小进度提示

      const url = `http://127.0.0.1:3001/api/library/progress/${taskId}`;
      console.log('[Library] 开始监听进度:', url);
      const evtSource = new EventSource(url);

      evtSource.onmessage = (e) => {
        console.log('[Library] SSE:', e.data);
        if (e.data === '[DONE]') { evtSource.close(); this.loadDocuments(); return; }
        try {
          const d = JSON.parse(e.data);
          if (d.error) {
            Utils.showToast(d.error, 'error');
            evtSource.close();
            return;
          }
          if (d.progress_pct !== undefined) {
            const pct = Math.max(2, Math.round(d.progress_pct));  // 最小显示 2%
            if (pctEl) pctEl.textContent = pct + '%';
            if (fillEl) fillEl.style.width = pct + '%';
          }
          const msg = d.detail?.message || d.status || '';
          if (stepEl && msg) stepEl.textContent = msg;

          if (d.status === 'completed') {
            Utils.showToast('资料处理完成！', 'success');
            evtSource.close();
            if (progressEl) progressEl.style.display = 'none';
            this.loadDocuments();
            if (DS.LibraryKnowledge) DS.LibraryKnowledge.loadCoverage();
            if (DS.LibraryGraph) DS.LibraryGraph.loadGraph();
          }
          if (d.status === 'failed') {
            const err = d.detail?.error || '未知错误';
            Utils.showToast('处理失败: ' + err, 'error');
            if (stepEl) stepEl.textContent = '失败: ' + err;
            evtSource.close();
            this.loadDocuments();
          }
        } catch (_) { }
      };
      evtSource.onerror = () => {
        console.log('[Library] SSE 连接关闭');
        evtSource.close();
        this.loadDocuments();
      };
    },

    async loadDocuments() {
      try {
        const resp = await fetch(`http://127.0.0.1:3001/api/library/documents?user_id=${DS.userId || 0}`);
        const data = await resp.json();
        if (!data.success) return;

        const listEl = DS.$('#libraryDocList');
        const emptyEl = DS.$('#libraryEmpty');
        const countEl = DS.$('#libraryDocCount');
        const docs = data.documents || [];

        if (countEl) countEl.textContent = docs.length + ' 份资料';
        if (emptyEl) emptyEl.style.display = docs.length ? 'none' : 'block';
        if (!listEl) return;

        listEl.innerHTML = docs.map(d => `
          <div class="library-doc-card">
            <i class="ri-file-pdf-line library-doc-icon" style="color:${d.doc_type==='textbook'?'#EF4444':d.doc_type==='rfc'?'#3B82F6':'#64748B'};"></i>
            <div class="library-doc-info">
              <div class="library-doc-title">${DS.escapeHtml(d.title||'')}</div>
              <div class="library-doc-meta">${d.doc_type||''} · ${d.chunk_count||0} 块 · ${(d.created_at||'').slice(0,10)}</div>
            </div>
            <span class="library-doc-status ${d.task_status||'completed'}">${d.task_status==='processing'?'处理中':d.task_status==='failed'?'失败':'已就绪'}</span>
            <span class="library-doc-export-wrap">
              <i class="ri-download-line library-doc-export" title="导出"></i>
              <span class="library-export-dropdown">
                <span class="library-export-item" data-export-doc="${d.doc_id}" data-export-fmt="md">Markdown (.md)</span>
                <span class="library-export-item" data-export-doc="${d.doc_id}" data-export-fmt="docx">Word (.docx)</span>
                <span class="library-export-item" data-export-doc="${d.doc_id}" data-export-fmt="pdf">PDF (.pdf)</span>
              </span>
            </span>
            <i class="ri-delete-bin-line library-doc-delete" data-doc-id="${d.doc_id}" title="删除"></i>
          </div>
        `).join('');

        // 绑定导出下拉菜单
        listEl.querySelectorAll('.library-doc-export').forEach(icon => {
          icon.addEventListener('click', (e) => {
            e.stopPropagation();
            e.preventDefault();
            const dropdown = icon.nextElementSibling;
            // 关闭其他打开的
            document.querySelectorAll('.library-export-dropdown.open').forEach(d => {
              if (d !== dropdown) d.classList.remove('open');
            });
            dropdown?.classList.toggle('open');
          });
        });
        listEl.querySelectorAll('.library-export-item').forEach(item => {
          item.addEventListener('click', (e) => {
            e.stopPropagation();
            const docId = item.dataset.exportDoc;
            const fmt = item.dataset.exportFmt;
            const url = `http://127.0.0.1:3001/api/library/documents/${docId}/export?format=${fmt}`;
            // 使用隐藏 <a> 触发下载，避免被浏览器拦截
            const a = document.createElement('a');
            a.href = url;
            a.download = '';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            // 关闭下拉
            item.closest('.library-export-dropdown')?.classList.remove('open');
          });
        });

        // 绑定删除事件
        listEl.querySelectorAll('.library-doc-delete').forEach(btn => {
          btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const docId = btn.dataset.docId;
            if (!confirm('确定删除此文档？知识块和向量索引将被同步清除。')) return;
            try {
              const r = await fetch(`http://127.0.0.1:3001/api/library/documents/${docId}?user_id=${DS.userId||0}`, { method: 'DELETE' });
              const j = await r.json();
              Utils.showToast(j.message || '已删除', j.success ? 'success' : 'error');
              if (j.success) { this.loadDocuments(); if (DS.LibraryKnowledge) DS.LibraryKnowledge.loadCoverage(); if (DS.LibraryGraph) DS.LibraryGraph.loadGraph(); }
            } catch (_) { Utils.showToast('网络错误', 'error'); }
          });
        });
      } catch (_) { }
    },
  };

  // ==================== 学习卡片模态框 ====================
  /**
   * LearningCardModal — 逐级展开知识点学习卡片
   *
   * 用法:
   *   DS.LearningCardModal.open(sub_topic_id)  → 打开知识点卡片
   *   DS.LearningCardModal.close()             → 关闭
   */
  DS.LearningCardModal = {
    _visible: false,
    _currentTopicId: null,
    _currentParentKp: null,
    _streamAbort: null,
    _fullContent: '',

    /** 打开知识点学习卡片 */
    async open(subTopicId) {
      this._currentTopicId = subTopicId;
      this._fullContent = '';
      if (this._streamAbort) { this._streamAbort.abort(); this._streamAbort = null; }

      // 显示加载状态
      this._showModal();
      this._setSlimContent('<div class="lc-loading"><i class="ri-loader-4-line ri-spin"></i> 正在生成学习卡片...</div>');
      this._setFullVisible(false);
      this._setActionsVisible(false);

      try {
        const resp = await fetch(
          `http://127.0.0.1:3001/api/library/learning-card?sub_topic_id=${subTopicId}&user_id=${DS.userId || 0}`
        );
        const data = await resp.json();
        if (!data.success) {
          this._setSlimContent(`<div class="lc-error">${DS.escapeHtml(data.message || '加载失败')}</div>`);
          return;
        }

        const card = data.card;
        this._currentParentKp = card.parent_kp;
        this._renderCard(card);
      } catch (err) {
        this._setSlimContent('<div class="lc-error">网络错误，请重试</div>');
      }
    },

    /** 关闭模态框 */
    close() {
      if (this._streamAbort) { this._streamAbort.abort(); this._streamAbort = null; }
      this._visible = false;
      this._currentTopicId = null;
      const overlay = DS.$('#learningCardOverlay');
      if (overlay) overlay.style.display = 'none';
    },

    // ---- 内部渲染 ----

    _showModal() {
      this._ensureDom();
      this._visible = true;
      DS.$('#learningCardOverlay').style.display = 'flex';
    },

    _ensureDom() {
      if (DS.$('#learningCardOverlay')) return;

      const html = `
        <div id="learningCardOverlay" class="lc-overlay" style="display:none;">
          <div class="lc-modal">
            <div class="lc-header">
              <div>
                <span id="lcTitle" class="lc-title"></span>
                <span id="lcParentKp" class="lc-parent-kp"></span>
              </div>
              <div class="lc-header-actions">
                <button id="lcBridgeExamBtn" class="lc-bridge-btn" title="去题库做相关题目">
                  <i class="ri-survey-line"></i> 去刷题
                </button>
                <button id="lcCloseBtn" class="lc-close-btn"><i class="ri-close-line"></i></button>
              </div>
            </div>
            <div class="lc-body">
              <div id="lcSlimContent" class="lc-slim"></div>
              <div id="lcFullContent" class="lc-full" style="display:none;"></div>
              <div id="lcStreaming" class="lc-streaming" style="display:none;"></div>
            </div>
            <div class="lc-footer" id="lcFooter" style="display:none;">
              <div class="lc-sources" id="lcSources"></div>
              <div class="lc-actions">
                <button id="lcExpandBtn" class="lc-expand-btn">
                  <i class="ri-arrow-down-s-line"></i> 展开完整讲解
                </button>
                <button id="lcGraphBtn" class="lc-bridge-btn" style="display:none;">
                  <i class="ri-node-tree"></i> 查看知识图谱
                </button>
              </div>
            </div>
          </div>
        </div>`;

      const temp = document.createElement('div');
      temp.innerHTML = html;
      document.body.appendChild(temp.firstElementChild);

      // 事件绑定
      DS.$('#lcCloseBtn').addEventListener('click', () => this.close());
      DS.$('#learningCardOverlay').addEventListener('click', (e) => {
        if (e.target === DS.$('#learningCardOverlay')) this.close();
      });
      DS.$('#lcExpandBtn').addEventListener('click', () => this._loadFullCard());
      DS.$('#lcBridgeExamBtn').addEventListener('click', () => this._bridgeToExam());
      DS.$('#lcGraphBtn').addEventListener('click', () => this._bridgeToGraph());

      // ESC 关闭
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && this._visible) this.close();
      });
    },

    _renderCard(card) {
      // 标题
      const titleEl = DS.$('#lcTitle');
      if (titleEl) titleEl.textContent = card.sub_topic_name || '';

      const kpEl = DS.$('#lcParentKp');
      if (kpEl) kpEl.textContent = card.parent_kp || '';

      // 精简版内容
      this._setSlimContent(this._formatCardContent(card.slim_content || ''));

      // 完整版已有缓存则显示
      if (card.full_content) {
        this._fullContent = card.full_content;
        this._setFullContent(this._formatCardContent(card.full_content));
        this._setFullVisible(true);
        DS.$('#lcExpandBtn').style.display = 'none';
      } else if (card.is_regenerating) {
        DS.$('#lcExpandBtn').textContent = '重新生成中...';
        DS.$('#lcExpandBtn').disabled = true;
      } else {
        DS.$('#lcExpandBtn').style.display = 'inline-flex';
        DS.$('#lcExpandBtn').disabled = false;
        DS.$('#lcExpandBtn').innerHTML = '<i class="ri-arrow-down-s-line"></i> 展开完整讲解';
      }

      // 来源文档
      this._renderSources(card.source_doc_ids || []);

      // 操作按钮
      this._setActionsVisible(true);
      DS.$('#lcGraphBtn').style.display = 'inline-flex';
    },

    /** 加载完整版卡片（SSE 流式） */
    async _loadFullCard() {
      if (!this._currentTopicId) return;

      const expandBtn = DS.$('#lcExpandBtn');
      if (expandBtn) { expandBtn.style.display = 'none'; }

      this._setFullVisible(true);
      this._setFullContent('<div class="lc-loading"><i class="ri-loader-4-line ri-spin"></i> AI 正在生成完整讲解...</div>');

      this._streamAbort = new AbortController();
      const tid = this._currentTopicId;

      try {
        const resp = await fetch(
          `http://127.0.0.1:3001/api/library/learning-card/stream?sub_topic_id=${tid}&user_id=${DS.userId || 0}`,
          { signal: this._streamAbort.signal }
        );

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let streamingEl = DS.$('#lcStreaming');
        let fullEl = DS.$('#lcFullContent');
        let loadingCleared = false;

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            const payload = line.slice(6);

            if (payload === '[DONE]') break;

            try {
              const d = JSON.parse(payload);
              if (d.error) {
                this._setFullContent(`<div class="lc-error">${DS.escapeHtml(d.error)}</div>`);
                return;
              }
              if (d.cached && d.full_content) {
                this._fullContent = d.full_content;
                this._setFullContent(this._formatCardContent(d.full_content));
                return;
              }
              if (d.chunk) {
                if (!loadingCleared) {
                  if (fullEl) fullEl.innerHTML = '';
                  loadingCleared = true;
                }
                this._fullContent += d.chunk;
                if (streamingEl) {
                  streamingEl.style.display = 'block';
                  streamingEl.innerHTML = this._formatCardContent(this._fullContent);
                }
              }
            } catch (_) {}
          }
        }

        // 写入正式区域
        if (streamingEl) streamingEl.style.display = 'none';
        this._setFullContent(this._formatCardContent(this._fullContent));

      } catch (err) {
        if (err.name !== 'AbortError') {
          this._setFullContent('<div class="lc-error">AI 生成中断，请重试</div>');
          if (expandBtn) { expandBtn.style.display = 'inline-flex'; expandBtn.disabled = false; }
        }
      } finally {
        this._streamAbort = null;
      }
    },

    /** 格式化卡片内容：将【标题】转为样式化区域 */
    _formatCardContent(text) {
      if (!text) return '';
      let html = DS.escapeHtml(text);
      // 分段
      html = html.replace(/\n\n/g, '</p><p>');
      html = '<p>' + html + '</p>';
      // 标题高亮 【xxx】
      html = html.replace(/【(.+?)】/g, '<span class="lc-section-tag">【$1】</span>');
      // 换行
      html = html.replace(/\n/g, '<br>');
      return html;
    },

    _setSlimContent(html) {
      const el = DS.$('#lcSlimContent');
      if (el) el.innerHTML = html;
    },

    _setFullContent(html) {
      const el = DS.$('#lcFullContent');
      if (el) { el.innerHTML = html; el.style.display = 'block'; }
    },

    _setFullVisible(visible) {
      const el = DS.$('#lcFullContent');
      if (el) el.style.display = visible ? 'block' : 'none';
    },

    _setActionsVisible(visible) {
      const el = DS.$('#lcFooter');
      if (el) el.style.display = visible ? 'flex' : 'none';
    },

    _renderSources(docIds) {
      const el = DS.$('#lcSources');
      if (!el) return;
      if (!docIds.length) { el.innerHTML = ''; return; }
      // 异步加载文档名称
      (async () => {
        try {
          const resp = await fetch(`http://127.0.0.1:3001/api/library/documents?user_id=${DS.userId || 0}`);
          const data = await resp.json();
          const docs = data.success ? (data.documents || []) : [];
          const names = docIds.map(id => {
            const d = docs.find(dd => dd.doc_id === id);
            return d ? d.title : `文档#${id}`;
          });
          el.innerHTML = '<span class="lc-sources-label">📚 来源：</span>' +
            names.map(n => `<span class="lc-source-tag">${DS.escapeHtml(n)}</span>`).join('');
        } catch (_) { el.innerHTML = ''; }
      })();
    },

    /** 桥接：跳转到题库做相关题目 */
    _bridgeToExam() {
      const parentKp = this._currentParentKp;
      if (!parentKp) {
        Utils.showToast('暂无关联题目', 'warning');
        return;
      }
      this.close();

      // 切换到刷题 Tab
      const examNav = document.querySelector('.nav-item[data-section="exam"]');
      if (examNav) examNav.click();

      // 通过 postMessage 发送筛选请求（exam.js 监听 message 事件）
      setTimeout(() => {
        window.postMessage({
          type: 'loadProblemsByFilter',
          payload: {
            knowledgePoints: [parentKp],
            count: 10,
          },
        }, '*');
      }, 300);
      Utils.showToast(`正在跳转到「${parentKp}」相关题目...`, 'success');
    },

    /** 桥接：高亮知识图谱中的对应节点 */
    _bridgeToGraph() {
      const parentKp = this._currentParentKp;
      if (!parentKp) return;
      this.close();

      // 如果已经在资料库 Tab，直接高亮；否则先切换
      const libNav = document.querySelector('.nav-item[data-section="library"]');
      if (libNav) libNav.click();

      // 图谱重新加载后尝试高亮
      setTimeout(() => {
        if (DS.LibraryGraph && DS.LibraryGraph._chart && DS.LibraryGraph._graphData?.nodes) {
          DS.LibraryGraph.highlightUncovered();
        }
      }, 800);
    },
  };

  // ==================== 系统知识库模块 (管理后台) ====================
  DS.SysLibrary = {
    _initialized: false,
    _uploading: false,

    init() {
      if (this._initialized) return;
      this._initialized = true;

      const uploadArea = DS.$('#adminLibUploadArea');
      const fileInput = DS.$('#adminLibFileInput');

      uploadArea?.addEventListener('click', () => fileInput?.click());
      fileInput?.addEventListener('change', () => {
        if (fileInput.files.length) this._handleFile(fileInput.files[0]);
      });

      uploadArea?.addEventListener('dragover', (e) => { e.preventDefault(); uploadArea.classList.add('drag-over'); });
      uploadArea?.addEventListener('dragleave', () => uploadArea.classList.remove('drag-over'));
      uploadArea?.addEventListener('drop', (e) => {
        e.preventDefault(); uploadArea.classList.remove('drag-over');
        const file = e.dataTransfer?.files?.[0];
        if (file) this._handleFile(file);
      });

      this.loadDocuments();
    },

    async _handleFile(file) {
      const maxMB = 200;
      if (file.size > maxMB * 1024 * 1024) { Utils.showToast('文件过大 (max 200MB)', 'error'); return; }
      const ext = file.name.split('.').pop()?.toLowerCase();
      if (!['pdf', 'docx'].includes(ext || '')) { Utils.showToast('仅支持 PDF/Word', 'error'); return; }
      if (this._uploading) { Utils.showToast('已有文件在上传中', 'warning'); return; }
      this._uploading = true;

      const formData = new FormData();
      formData.append('file', file);
      formData.append('user_id', '0'); // 系统知识库
      formData.append('doc_type', 'textbook');
      formData.append('title', file.name);

      try {
        const resp = await fetch('http://127.0.0.1:3001/api/library/upload', { method: 'POST', body: formData });
        const data = await resp.json();
        if (data.success) {
          Utils.showToast('已上传，正在后台处理...', 'success');
          this._watchProgress(data.task_id);
        } else { Utils.showToast(data.message || '上传失败', 'error'); }
      } catch (_) { Utils.showToast('网络错误', 'error'); }
      this._uploading = false;
    },

    _watchProgress(taskId) {
      const progEl = DS.$('#adminLibProgress');
      const stepEl = DS.$('#adminLibProgressStep');
      const pctEl = DS.$('#adminLibProgressPct');
      const fillEl = DS.$('#adminLibProgressFill');
      if (progEl) progEl.style.display = 'block';
      if (stepEl) stepEl.textContent = '等待处理...';
      if (pctEl) pctEl.textContent = '0%';
      if (fillEl) fillEl.style.width = '2%';

      const url = `http://127.0.0.1:3001/api/library/progress/${taskId}`;
      console.log('[SysLib] 开始监听:', url);
      const es = new EventSource(url);
      es.onmessage = (e) => {
        console.log('[SysLib] SSE:', e.data);
        if (e.data === '[DONE]') { es.close(); this.loadDocuments(); return; }
        try {
          const d = JSON.parse(e.data);
          if (d.error) { Utils.showToast(d.error, 'error'); es.close(); return; }
          if (d.progress_pct !== undefined) {
            const pct = Math.max(2, Math.round(d.progress_pct));
            if (pctEl) pctEl.textContent = pct + '%';
            if (fillEl) fillEl.style.width = pct + '%';
          }
          const msg = d.detail?.message || d.status || '';
          if (stepEl && msg) stepEl.textContent = msg;
          if (d.status === 'completed') { Utils.showToast('系统资料处理完成！', 'success'); es.close(); if (progEl) progEl.style.display = 'none'; this.loadDocuments(); }
          if (d.status === 'failed') { const err = d.detail?.error || '未知'; Utils.showToast('处理失败: ' + err, 'error'); if (stepEl) stepEl.textContent = '失败: ' + err; es.close(); this.loadDocuments(); }
        } catch (_) { }
      };
      es.onerror = () => { console.log('[SysLib] SSE 关闭'); es.close(); this.loadDocuments(); };
    },

    async loadDocuments() {
      try {
        const resp = await fetch('http://127.0.0.1:3001/api/library/documents?user_id=0');
        const data = await resp.json();
        const listEl = DS.$('#adminLibDocList');
        const emptyEl = DS.$('#adminLibEmpty');
        if (!data.success || !listEl) return;
        const docs = data.documents || [];
        if (emptyEl) emptyEl.style.display = docs.length ? 'none' : 'block';
        listEl.innerHTML = docs.map(d => `
          <div class="library-doc-card">
            <i class="ri-file-pdf-line library-doc-icon" style="color:#EF4444;"></i>
            <div class="library-doc-info">
              <div class="library-doc-title">${DS.escapeHtml(d.title||'')}</div>
              <div class="library-doc-meta">${d.doc_type||''} · ${d.chunk_count||0} 块 · ${(d.created_at||'').slice(0,10)}</div>
            </div>
            <span class="library-doc-status ${d.task_status||'completed'}">${d.task_status==='processing'?'处理中':d.task_status==='failed'?'失败':'已就绪'}</span>
            <span class="library-doc-export-wrap">
              <i class="ri-download-line library-doc-export" title="导出"></i>
              <span class="library-export-dropdown">
                <span class="library-export-item" data-export-doc="${d.doc_id}" data-export-fmt="md">Markdown (.md)</span>
                <span class="library-export-item" data-export-doc="${d.doc_id}" data-export-fmt="docx">Word (.docx)</span>
                <span class="library-export-item" data-export-doc="${d.doc_id}" data-export-fmt="pdf">PDF (.pdf)</span>
              </span>
            </span>
          </div>
        `).join('');

        // 绑定导出下拉菜单
        listEl.querySelectorAll('.library-doc-export').forEach(icon => {
          icon.addEventListener('click', (e) => {
            e.stopPropagation();
            e.preventDefault();
            const dropdown = icon.nextElementSibling;
            document.querySelectorAll('.library-export-dropdown.open').forEach(d => {
              if (d !== dropdown) d.classList.remove('open');
            });
            dropdown?.classList.toggle('open');
          });
        });
        listEl.querySelectorAll('.library-export-item').forEach(item => {
          item.addEventListener('click', (e) => {
            e.stopPropagation();
            const docId = item.dataset.exportDoc;
            const fmt = item.dataset.exportFmt;
            const url = `http://127.0.0.1:3001/api/library/documents/${docId}/export?format=${fmt}`;
            const a = document.createElement('a');
            a.href = url;
            a.download = '';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            item.closest('.library-export-dropdown')?.classList.remove('open');
          });
        });
      } catch (_) { }
    },
  };
})();
