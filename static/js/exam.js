(function () {
  const problemsContainer = document.getElementById('problemsContainer');
  const reloadBtn = document.getElementById('reloadBtn');
  const viewProfileBtn = document.getElementById('viewProfileBtn');
  const profileCard = document.getElementById('profileCard');
  const profileContainer = document.getElementById('profileContainer');
  const strengthRow = document.getElementById('strengthRow');
  const trendRow = document.getElementById('strengthTrend');

  const logoutBtn = document.getElementById('logoutBtn');
  const welcomeName = document.getElementById('welcomeName');
  const countInput = document.getElementById('countInput');
  const knowledgeFilterList = document.getElementById('knowledgeFilterList');
  const kpSelectAll = document.getElementById('kpSelectAll');
  const kpSelectCount = document.getElementById('kpSelectCount');
  const sessionReportCard = document.getElementById('sessionReportCard');
  const sessionReport = document.getElementById('sessionReport');

  const userName = storageManager.getCurrentUserName();
  const userId = storageManager.getCurrentUserId(); // 可能为 null（游客）

  // 设置欢迎信息
  if (welcomeName) {
    welcomeName.textContent = userName ? `欢迎，${userName}` : '游客模式';
  }

  if (!storageManager.isLoggedIn() && !userId) {
    // 兼容：没登录也能做随机题
    console.warn('游客模式：将获取随机题目');
  }

  logoutBtn?.addEventListener('click', () => {
    storageManager.clearCurrentUser();
    window.location.href = 'login.html';
  });

  // 当前批次的答题统计
  let currentProblems = [];
  let answeredCount = 0;
  let correctCount = 0;

  /**
   * 解析题量输入
   * @returns {number} 合法题量（默认5）
   */
  function parseCount() {
    console.log('countInput元素:', countInput); // 调试信息
    // 优先取当前值
    const raw = (countInput?.value ?? '').trim();
    console.log('用户输入的题量原始值:', raw); // 调试信息

    // 将全角数字（０-９）规范化为半角数字（0-9），并移除非数字字符
    const normalized = normalizeToAsciiDigits(raw).replace(/[^0-9]/g, '');
    console.log('规范化后的数字串:', normalized);

    // 如果输入框为空或规范化后为空，使用默认值5
    if (!normalized) {
      console.log('输入为空或无法解析，使用默认题量: 5');
      return 5;
    }

    const n = Number(normalized);
    console.log('转换后的数字:', n); // 调试信息
    if (!Number.isInteger(n) || n <= 0) {
      console.log('使用默认题量: 5，原因: 不是正整数或小于等于0');
      return 5;
    }
    const finalCount = Math.min(n, 50); // 限制最大 50
    console.log('最终题量:', finalCount);
    return finalCount;
  }

  /**
   * 工具：将字符串中的全角数字转换为半角数字
   * @param {string} s 原始字符串
   * @returns {string} 替换后的字符串
   */
  function normalizeToAsciiDigits(s) {
    if (!s) return '';
    // 将全角0-9 (U+FF10 - U+FF19) 映射到 ASCII 0-9 (U+0030 - U+0039)
    return s.replace(/[\uFF10-\uFF19]/g, ch => String.fromCharCode(ch.charCodeAt(0) - 0xFF10 + 0x30));
  }

  /**
   * 实时预览：根据当前输入更新工具栏中的“即将请求”显示
   */
  function updateRequestStatusPreview() {
    try {
      const upcoming = parseCount();
      const toolbar = document.querySelector('.toolbar');
      const existing = document.getElementById('requestStatus');
      const status = existing || document.createElement('div');
      status.id = 'requestStatus';
      status.style.fontSize = '12px';
      status.style.color = '#555';
      status.style.marginRight = 'auto';
      const qs = new URLSearchParams();
      qs.set('count', upcoming);
      if (userId) qs.set('user_id', userId);
      const selectedKps = getSelectedKnowledgePoints();
      const useFilter = !!userId && selectedKps.length > 0;
      if (useFilter) qs.set('knowledge_points', selectedKps.join(','));
      const base = (typeof apiClient !== 'undefined' && apiClient?.baseUrl) ? apiClient.baseUrl : window.location.origin;
      const path = useFilter ? '/api/problems/filter' : '/api/problems';
      const previewUrl = `${base}${path}?${qs.toString()}`;
      status.textContent = `即将请求：count=${upcoming}${userId ? `, user_id=${userId}` : ''} ｜ URL: ${previewUrl}`;
      if (!existing) toolbar?.insertBefore(status, toolbar.firstChild);
    } catch (_) {}
  }

  function getSelectedKnowledgePoints() {
    if (!knowledgeFilterList) return [];
    const inputs = Array.from(knowledgeFilterList.querySelectorAll('input[type="checkbox"]'));
    return inputs.filter(i => i.checked).map(i => i.value).filter(v => v);
  }

  function updateKpSelectCount() {
    if (!kpSelectCount) return;
    const selected = getSelectedKnowledgePoints();
    kpSelectCount.textContent = `已选 ${selected.length} 个`;
  }

  function syncSelectAllState() {
    if (!kpSelectAll || !knowledgeFilterList) return;
    const inputs = Array.from(knowledgeFilterList.querySelectorAll('input[type="checkbox"]'));
    if (inputs.length === 0) {
      kpSelectAll.checked = false;
      return;
    }
    kpSelectAll.checked = inputs.every(i => i.checked);
  }

  function renderKnowledgePoints(items = []) {
    if (!knowledgeFilterList) return;
    knowledgeFilterList.innerHTML = '';
    if (!Array.isArray(items) || items.length === 0) {
      knowledgeFilterList.textContent = '暂无知识点';
      if (kpSelectAll) kpSelectAll.checked = false;
      updateKpSelectCount();
      return;
    }
    const frag = document.createDocumentFragment();
    items.forEach(kp => {
      const label = document.createElement('label');
      label.className = 'kp-filter-item';
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.value = String(kp);
      input.checked = true;
      input.addEventListener('change', () => {
        syncSelectAllState();
        updateKpSelectCount();
        updateRequestStatusPreview();
      });
      const text = document.createElement('span');
      text.textContent = String(kp);
      label.appendChild(input);
      label.appendChild(text);
      frag.appendChild(label);
    });
    knowledgeFilterList.appendChild(frag);
    syncSelectAllState();
    updateKpSelectCount();
  }

  async function initKnowledgePoints() {
    try {
      const resp = await apiClient.getKnowledgePoints();
      const items = (resp && resp.success && Array.isArray(resp.items)) ? resp.items : [];
      renderKnowledgePoints(items);
    } catch (e) {
      renderKnowledgePoints([]);
    }
    updateRequestStatusPreview();
  }

  /**
   * 加载题目列表（根据输入的题量）
   * 从后端获取题目，并渲染到页面
   */
  async function loadProblems() {
    // 重置统计
    answeredCount = 0;
    correctCount = 0;
    currentProblems = [];
    if (sessionReportCard) sessionReportCard.style.display = 'none';
    if (sessionReport) sessionReport.innerHTML = '';

    // 确保输入法（IME）内容提交
    try { countInput?.blur(); } catch (_) {}

    const count = parseCount();
    console.log('[loadProblems] 即将请求题目数量 count =', count); // 调试

    // 在工具栏里显示这次将要请求的参数与URL
    try {
      const toolbar = document.querySelector('.toolbar');
      const existing = document.getElementById('requestStatus');
      const status = existing || document.createElement('div');
      status.id = 'requestStatus';
      status.style.fontSize = '12px';
      status.style.color = '#555';
      status.style.marginRight = 'auto';
      // 组合URL（与 api.js 中一致）
      const qs = new URLSearchParams();
      qs.set('count', count);
      if (userId) qs.set('user_id', userId);
      const selectedKps = getSelectedKnowledgePoints();
      const useFilter = !!userId && selectedKps.length > 0;
      if (useFilter) qs.set('knowledge_points', selectedKps.join(','));
      const base = (typeof apiClient !== 'undefined' && apiClient?.baseUrl) ? apiClient.baseUrl : window.location.origin;
      const path = useFilter ? '/api/problems/filter' : '/api/problems';
      const previewUrl = `${base}${path}?${qs.toString()}`;
      status.textContent = `即将请求：count=${count}${userId ? `, user_id=${userId}` : ''} ｜ URL: ${previewUrl}`;
      if (!existing) {
        toolbar?.insertBefore(status, toolbar.firstChild);
      }
    } catch (_) {}

    problemsContainer.innerHTML = '正在获取题目...';
    try {
      const selectedKps = getSelectedKnowledgePoints();
      let resp;
      if (userId && selectedKps.length > 0) {
        resp = await apiClient.getProblemsByFilter(userId, count, {
          knowledgePoints: selectedKps,
          staleDays: 30
        });
      } else {
        resp = await apiClient.getProblems(userId, count);
      }
      if (!resp || !resp.success) {
        problemsContainer.innerHTML = (resp && resp.message) || '获取题目失败';
        return;
      }
      const list = Array.isArray(resp.problems) ? resp.problems : [];
      currentProblems = list;
      renderProblems(list, count);
    } catch (e) {
      console.error(e);
      problemsContainer.innerHTML = '获取题目时发生错误';
    }
  }

  /**
   * 解析选择题选项并分离题干
   * @param {string} problemText 题目文本
   * @returns {Object} {stem: string, options: Array} 题干和选项数组
   */
  function parseMultipleChoiceOptions(problemText) {
    const options = [];
    const lines = problemText.split('\n');
    const stemLines = [];
    
    for (const line of lines) {
      const match = line.match(/^([A-D])\s*\.\s*(.+)$/);
      if (match) {
        options.push({
          letter: match[1],
          text: match[2].trim()
        });
      } else {
        // 不是选项的行，加入题干
        stemLines.push(line);
      }
    }
    
    return {
      stem: stemLines.join('\n').trim(),
      options: options
    };
  }

  /**
   * 渲染题目卡片并绑定提交事件
   * @param {Array} problems 题目数组
   * @param {number} requestedCount 本次请求的题量（用于对照显示）
   */
  function renderProblems(problems, requestedCount) {
    console.log('[exam] renderProblems 被调用，题目数量:', problems ? problems.length : 0);
    console.log('[exam] 题目数据:', problems);
    
    if (!problems || problems.length === 0) {
      console.warn('[exam] renderProblems: 没有题目数据');
      problemsContainer.innerHTML = '<div class="no-problems-message">暂无题目</div>';
      return;
    }
    
    console.log('[exam] 开始清空容器并渲染题目');
    problemsContainer.innerHTML = '';

    // 在题目列表上方显示请求与返回的数量，方便核对
    const statusBar = document.createElement('div');
    statusBar.className = 'meta';
    const returned = problems.length;
    let tip = '';
    if (typeof requestedCount === 'number') {
      if (returned < requestedCount) {
        tip = '（数据库可用题目不足，已返回最大可用数量）';
      } else if (returned > requestedCount) {
        tip = '（返回数量大于请求，可能是后端逻辑问题）';
      }
      statusBar.textContent = `本次请求：${requestedCount} 道，实际返回：${returned} 道 ${tip}`;
    } else {
      statusBar.textContent = `实际返回：${returned} 道`;
    }
    problemsContainer.appendChild(statusBar);

    problems.forEach((p, idx) => {
      const card = document.createElement('div');
      card.className = 'problem';
      
      // 检测是否为选择题（包含A. B. C. D.格式的选项）
      const isMultipleChoice = /[A-D]\.[^\n]*/.test(p.problem);
      
      let stemContent = '';
      let answerSection = '';
      
      if (isMultipleChoice) {
        // 解析选择题的题干和选项
        const parsed = parseMultipleChoiceOptions(p.problem);
        stemContent = escapeHtml(parsed.stem);
        
        const optionsHtml = parsed.options.map(opt => 
          `<div class="option-item">
            <input type="radio" name="ans_${p.problem_id}" value="${opt.letter}" id="opt_${p.problem_id}_${opt.letter}" />
            <label for="opt_${p.problem_id}_${opt.letter}">${opt.letter}. ${escapeHtml(opt.text)}</label>
          </div>`
        ).join('');
        
        answerSection = `
          <div class="options-container">
            ${optionsHtml}
          </div>
          <div class="answer-row">
            <button class="btn" id="btn_${p.problem_id}">提交答案</button>
          </div>
        `;
      } else {
        // 非选择题，保持原有的输入框形式
        stemContent = escapeHtml(p.problem);
        answerSection = `
          <div class="answer-row">
            <input class="answer-input" id="ans_${p.problem_id}" placeholder="输入答案" />
            <button class="btn" id="btn_${p.problem_id}">提交答案</button>
          </div>
        `;
      }
      
      card.innerHTML = `
        <div class="meta">
          <span>题目编号：${p.problem_num || p.problem_id}</span>
          <span class="kp">知识点：${p.knowledge_point || '未知'}</span>
          <span class="kp">难度：${p.difficulty || '未知'}</span>
        </div>
        <div class="stem">${stemContent}</div>
        ${answerSection}
        <div class="result" id="res_${p.problem_id}"></div>
      `;
      problemsContainer.appendChild(card);
      const btn = card.querySelector(`#btn_${p.problem_id}`);
      btn.addEventListener('click', async () => {
        const resultDiv = card.querySelector(`#res_${p.problem_id}`);
        let val = '';
        
        if (isMultipleChoice) {
          // 获取选中的单选按钮值
          const selectedOption = card.querySelector(`input[name="ans_${p.problem_id}"]:checked`);
          val = selectedOption ? selectedOption.value : '';
        } else {
          // 获取输入框的值
          const input = card.querySelector(`#ans_${p.problem_id}`);
          val = (input.value || '').trim();
        }
        
        if (!val) {
          resultDiv.textContent = isMultipleChoice ? '请先选择答案' : '请先输入答案';
          resultDiv.className = 'result bad';
          return;
        }
        try {
          const resp = await apiClient.submitAnswer(userId || 0, p.problem_id, val);
          if (!resp || !resp.success) {
            resultDiv.textContent = (resp && resp.message) || '提交失败';
            resultDiv.className = 'result bad';
            return;
          }
          if (resp.is_correct) {
            resultDiv.textContent = '回答正确！';
            resultDiv.className = 'result ok';
            correctCount += 1;
          } else {
            resultDiv.textContent = `回答错误，正确答案：${resp.correct_answer}`;
            resultDiv.className = 'result bad';
          }
          // 标记已答
          if (!btn.disabled) {
            answeredCount += 1;
            btn.disabled = true;
          }
          // 如果全部答完，生成本次报告
          if (answeredCount >= currentProblems.length) {
            generateSessionReport();
          }
        } catch (e) {
          console.error(e);
          const resultDiv = card.querySelector(`#res_${p.problem_id}`);
          resultDiv.textContent = '提交答案时发生错误';
          resultDiv.className = 'result bad';
        }
      });
    });
  }

  /**
   * 生成并展示本次会话的简略能力报告
   * - 统计正确率、题量
   * - 如果用户已登录，可提示去查看能力画像
   */
  function generateSessionReport() {
    if (!sessionReportCard || !sessionReport) return;
    const total = currentProblems.length || 0;
    const accuracy = total ? Math.round((correctCount / total) * 100) : 0;

    const summary = document.createElement('div');
    summary.style.lineHeight = '1.8';
    summary.innerHTML = `
      <div>本次作答：<strong>${total}</strong> 道，正确 <strong>${correctCount}</strong> 道，正确率 <strong>${accuracy}%</strong></div>
      <div style="margin-top:6px;color:#444;">建议：优先复习错题涉及的知识点，点击“查看我的能力画像”获取更全面的长期画像。</div>
    `;

    sessionReport.innerHTML = '';
    sessionReport.appendChild(summary);
    sessionReportCard.style.display = '';
    // 滚动到报告区域
    sessionReportCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  reloadBtn?.addEventListener('click', loadProblems);

  /**
   * 一键提交：批量提交本页“已填写”的答案
   * - 仅提交已填写的题目，空白答案会被跳过，不计入已答数量
   * - 与逐题提交保持一致的判题与UI反馈逻辑
   * - 完成后若全部题目都已作答，则生成本次报告
   */
  async function submitAllFilledAnswers() {
    // 提交前，尝试提交输入法（IME）的未确认内容
    try { document.activeElement && document.activeElement.blur(); } catch (_) {}
    try { document.querySelectorAll('.answer-input').forEach(el => el.blur()); } catch (_) {}

    // 收集所有已填写的答案
    const tasks = [];
    for (const p of currentProblems) {
      const btn = document.getElementById(`btn_${p.problem_id}`);
      const resultDiv = document.getElementById(`res_${p.problem_id}`);
      
      // 检查是否为选择题
      const isMultipleChoice = p.problem && /^[\s\S]*[ABCD]\s*[.．]/.test(p.problem);
      let val = '';
      
      if (isMultipleChoice) {
        // 获取选中的单选按钮值
        const selectedOption = document.querySelector(`input[name="ans_${p.problem_id}"]:checked`);
        val = selectedOption ? selectedOption.value : '';
      } else {
        // 获取输入框的值
        const input = document.getElementById(`ans_${p.problem_id}`);
        val = (input?.value || '').trim();
      }
      
      if (!val) continue; // 跳过空白答案
      tasks.push({ p, val, btn, resultDiv });
    }

    if (!tasks.length) {
      try { alert('没有可提交的答案，请先填写再一键提交。'); } catch (_) {}
      return;
    }

    // 设置一键提交按钮加载状态
    const submitAllBtn = document.getElementById('submitAllBtn');
    let oldText = '';
    if (submitAllBtn) {
      oldText = submitAllBtn.textContent;
      submitAllBtn.textContent = '提交中...';
      submitAllBtn.disabled = true;
    }

    // 并发提交所有已填写的答案
    let okCount = 0;
    try {
      const results = await Promise.allSettled(
        tasks.map(t => apiClient.submitAnswer(userId || 0, t.p.problem_id, t.val))
      );

      results.forEach((r, i) => {
        const { p, btn, resultDiv } = tasks[i];
        if (r.status === 'fulfilled' && r.value && r.value.success) {
          const resp = r.value;
          if (resp.is_correct) {
            resultDiv.textContent = '回答正确！';
            resultDiv.className = 'result ok';
            correctCount += 1;
          } else {
            resultDiv.textContent = `回答错误，正确答案：${resp.correct_answer}`;
            resultDiv.className = 'result bad';
          }
          // 标记已答（避免重复累计）
          if (btn && !btn.disabled) {
            answeredCount += 1;
            btn.disabled = true;
          }
          okCount += 1;
        } else {
          // 单题提交失败
          if (resultDiv) {
            const msg = (r.status === 'fulfilled' && r.value && r.value.message) ? r.value.message : '提交失败';
            resultDiv.textContent = msg;
            resultDiv.className = 'result bad';
          }
        }
      });

      // 若全部题目都已作答，则生成会话报告
      if (answeredCount >= currentProblems.length) {
        generateSessionReport();
      }

      // 简要提示
      try { console.log(`[submitAll] 已提交 ${okCount}/${tasks.length} 题`); } catch (_) {}
    } catch (e) {
      console.error(e);
      try { alert('一键提交过程中发生错误，请稍后重试'); } catch (_) {}
    } finally {
      if (submitAllBtn) {
        submitAllBtn.textContent = oldText || '一键提交已填写答案';
        submitAllBtn.disabled = false;
      }
    }
  }

  // 动态在工具栏加入“一键提交已填写答案”按钮（避免修改HTML）
  (function injectSubmitAllButton() {
    const toolbar = document.querySelector('.toolbar');
    if (!toolbar) return;
    if (document.getElementById('submitAllBtn')) return; // 已存在

    const btn = document.createElement('button');
    btn.id = 'submitAllBtn';
    btn.className = 'btn';
    btn.textContent = '一键提交已填写答案';
    btn.addEventListener('click', submitAllFilledAnswers);

    // 插入到“开始/换一批”按钮之后
    if (reloadBtn && reloadBtn.parentNode === toolbar) {
      toolbar.insertBefore(btn, reloadBtn.nextSibling);
    } else {
      toolbar.appendChild(btn);
    }
  })();

  viewProfileBtn?.addEventListener('click', async () => {
    if (!userId) {
      alert('游客模式无法查看能力画像，请先登录。');
      return;
    }
    try {
      profileCard.style.display = '';
      profileContainer.innerHTML = '正在获取能力画像...';
      strengthRow.innerHTML = '';
      trendRow && (trendRow.innerHTML = '');
      const resp = await apiClient.getUserProfile(userId);

      // 不再提前返回：即使失败，也尝试获取趋势图
      let profile = null;
      let analysis = null;
      if (!resp || !resp.success) {
        profileContainer.innerHTML = (resp && resp.message) || '获取失败';
      } else {
        ({ profile, analysis } = resp);
      }

      // 展示用户整体实力（user_strength）
      (function renderUserStrength() {
        const strength = (profile && typeof profile.user_strength === 'number')
          ? profile.user_strength : Number(profile?.user_strength) || 0.5;
        const safeStrength = Math.max(0, Math.min(1, strength));
        const percent = Math.round(safeStrength * 100);
        const { label, color } = mapStrengthToLevelAndColor(safeStrength);
        strengthRow.innerHTML = `
          <div style="margin: 4px 0;">
            <span style="font-weight:600;color:#111;">整体实力：</span>
            <span style="color:#111;">${safeStrength.toFixed(2)}（${percent}%）</span>
            <span style="margin-left:8px;padding:2px 6px;border-radius:9999px;background:${color}20;color:${color};font-size:12px;">${label}</span>
          </div>
          <div style="height:10px;width:100%;background:#f1f5f9;border-radius:6px;margin-top:6px;">
            <div style="height:10px;border-radius:6px;background:${color};width:${percent}%;transition:width .3s ease;"></div>
          </div>
        `;
      })();

      // 渲染能力画像
      const abilities = (profile && profile.abilities)
        ? profile.abilities
        : (profile && typeof profile === 'object' ? profile : {});
      const entries = Object.entries(abilities).filter(([_, v]) => typeof v === 'number' && isFinite(v));
      if (entries.length === 0) {
        profileContainer.innerHTML = '暂无能力画像数据，请先多做几道题。';
      } else {
        entries.sort((a, b) => b[1] - a[1]);
        const list = document.createElement('div');
        entries.forEach(([kp, val]) => {
          const valueNum = Number(val) || 0;
          const percent = Math.max(0, Math.min(100, Math.round(valueNum * 100)));
          const row = document.createElement('div');
          row.style.margin = '6px 0';
          row.innerHTML = `
            <strong>${kp}</strong>：${valueNum.toFixed(2)}
            <div style="height:8px;width:100%;background:#f1f5f9;border-radius:6px;margin-top:4px;">
              <div style="height:8px;border-radius:6px;background:#2563eb;width:${percent}%;"></div>
            </div>
          `;
          list.appendChild(row);
        });
        profileContainer.innerHTML = '';
        profileContainer.appendChild(list);
      }

      // 渲染 AI 分析
      if (analysis) {
        const ana = document.createElement('div');
        ana.style.marginTop = '12px';
        ana.style.whiteSpace = 'pre-wrap';
        ana.textContent = String(analysis);
        profileContainer.appendChild(ana);
      }

      // 获取并渲染实力趋势（即使画像获取失败也尝试）
      try {
        if (trendRow) {
          const trendResp = await apiClient.getUserStrengthTrend(userId);
          if (trendResp && trendResp.success && Array.isArray(trendResp.trend)) {
            renderMiniTrendChart(trendRow, trendResp.trend);
          } else {
            trendRow.textContent = (trendResp && trendResp.message) || '无法获取实力趋势';
          }
        }
      } catch (e) {
        console.error(e);
        trendRow && (trendRow.textContent = '获取实力趋势时发生错误');
      }
    } catch (e) {
      console.error(e);
      profileContainer.innerHTML = '获取能力画像时发生错误';
    }
  });

  /** 小工具：转义 HTML */
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
  }

  // 首次不自动加载，等待用户点击“开始/换一批”，以便自定义题量
  // 如需保持原行为，可取消下一行注释
  // loadProblems();
  kpSelectAll?.addEventListener('change', () => {
    const checked = kpSelectAll.checked;
    if (knowledgeFilterList) {
      const inputs = Array.from(knowledgeFilterList.querySelectorAll('input[type="checkbox"]'));
      inputs.forEach(i => { i.checked = checked; });
    }
    updateKpSelectCount();
    updateRequestStatusPreview();
  });
  initKnowledgePoints();

  // 实时更新“即将请求”预览，避免IME未提交导致误判
  countInput?.addEventListener('input', updateRequestStatusPreview);
  countInput?.addEventListener('compositionend', updateRequestStatusPreview);

  /**
   * 对外暴露必要的 API，供 IIFE 外部（例如跨窗口消息处理器）访问
   * - renderProblems: 渲染题目列表
   * - getProblemsContainer: 获取题目容器元素
   * - setCurrentProblems: 设置当前题目数组
   */
  window.__examAPI = {
    /** 渲染题目列表 */
    renderProblems: renderProblems,
    /** 获取题目容器元素 */
    getProblemsContainer: () => problemsContainer,
    /** 设置当前题目列表（供外部消息处理器更新会话状态） */
    setCurrentProblems: (list) => { currentProblems = Array.isArray(list) ? list : []; }
  };
})();

/**
 * 将实力值映射到等级标签与颜色
 * 区间：
 * - 0.00~0.39：初级（红色）
 * - 0.40~0.69：中级（橙色）
 * - 0.70~0.89：高级（绿色）
 * - 0.90~1.00：专家（深绿色）
 */
function mapStrengthToLevelAndColor(value) {
  const v = Math.max(0, Math.min(1, Number(value) || 0));
  if (v < 0.4) return { label: '初级', color: '#ef4444' };
  if (v < 0.7) return { label: '中级', color: '#f59e0b' };
  if (v < 0.9) return { label: '高级', color: '#22c55e' };
  return { label: '专家', color: '#15803d' };
}

/**
 * 渲染迷你折线图（sparkline）
 * trendData: Array<{t: string, value: number}>
 */
function renderMiniTrendChart(container, trendData) {
  container.innerHTML = '';
  if (!Array.isArray(trendData) || trendData.length === 0) {
    container.textContent = '暂无实力趋势数据';
    return;
  }
  const n = trendData.length;
  const wrapper = document.createElement('div');
  wrapper.style.marginTop = '6px';
  const title = document.createElement('div');
  title.style.fontWeight = '600';
  title.style.marginBottom = '4px';
  title.textContent = '实力趋势（按会话）';
  wrapper.appendChild(title);

  const svgNS = 'http://www.w3.org/2000/svg';
  const width = Math.max(240, container.clientWidth || 0);
  const height = 64;
  const pad = 6;
  const w = width - pad * 2;
  const h = height - pad * 2;

  const svg = document.createElementNS(svgNS, 'svg');
  svg.setAttribute('width', String(width));
  svg.setAttribute('height', String(height));
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
  svg.style.background = '#f8fafc';
  svg.style.borderRadius = '6px';

  // 计算路径
  const points = trendData.map((d, i) => {
    const x = pad + (n === 1 ? w / 2 : (i * w) / (n - 1));
    const val = Math.max(0, Math.min(1, Number(d.value) || 0));
    const y = pad + (1 - val) * h;
    return { x, y };
  });
  let d = '';
  points.forEach((p, i) => {
    d += (i === 0 ? 'M' : 'L') + p.x + ' ' + p.y + ' ';
  });

  const path = document.createElementNS(svgNS, 'path');
  path.setAttribute('d', d.trim());
  path.setAttribute('fill', 'none');
  path.setAttribute('stroke', '#0ea5e9');
  path.setAttribute('stroke-width', '2');
  svg.appendChild(path);

  // 终点高亮
  const last = points[points.length - 1];
  const endDot = document.createElementNS(svgNS, 'circle');
  endDot.setAttribute('cx', String(last.x));
  endDot.setAttribute('cy', String(last.y));
  endDot.setAttribute('r', '3');
  endDot.setAttribute('fill', '#0ea5e9');
  endDot.setAttribute('stroke', '#0369a1');
  endDot.setAttribute('stroke-width', '1');
  svg.appendChild(endDot);

  wrapper.appendChild(svg);
  container.appendChild(wrapper);
}

/**
   * 处理父页面消息：支持按过滤条件加载题目，或直接设置题目列表
   */
  window.addEventListener('message', async (evt) => {
    try {
      const data = evt && evt.data;
      if (!data || typeof data !== 'object') return;
      const { type, payload } = data;

      // 访问从 IIFE 暴露出来的渲染 API 与容器
      const api = window.__examAPI;
      if (!api || typeof api.renderProblems !== 'function' || typeof api.getProblemsContainer !== 'function') {
        console.error('[exam] __examAPI 未初始化，无法处理消息');
        return;
      }
      const container = api.getProblemsContainer();

      if (type === 'loadProblemsByFilter') {
        const count = Math.max(1, Math.min(50, parseInt(payload?.count || 5)));
        const knowledgePoints = Array.isArray(payload?.knowledgePoints) ? payload.knowledgePoints : [];
        const difficulties = Array.isArray(payload?.difficulties) ? payload.difficulties : [];
        
        // 重新获取当前用户ID，确保是最新的
        const currentUserId = storageManager.getCurrentUserId();
        console.log('[exam] 收到筛选请求:', { count, knowledgePoints, difficulties, currentUserId });
        
        // 检查用户登录状态
        if (!currentUserId) {
          console.warn('[exam] 用户未登录，无法进行筛选');
          container.innerHTML = '<div class="error-message">请先登录后再使用筛选功能</div>';
          return;
        }
        
        // 显示加载状态
        container.innerHTML = '<div class="loading-message">🔄 正在获取匹配题目，请稍候...</div>';
        
        try {
          console.log('[exam] 开始调用API...');
         const resp = await apiClient.getProblemsByFilter(currentUserId, count, {
  knowledgePoints,
  difficulties,
  staleDays: 30   // 和普通 /api/problems 保持一致
});

          console.log('[exam] API响应完整数据:', JSON.stringify(resp, null, 2));
          
          if (resp && resp.success) {
            if (Array.isArray(resp.problems) && resp.problems.length > 0) {
              console.log(`[exam] 成功获取 ${resp.problems.length} 道题目，开始渲染`);
              api.setCurrentProblems(resp.problems);
              api.renderProblems(resp.problems, count);
              console.log('[exam] 题目渲染完成');
            } else {
              console.warn('[exam] API返回成功但没有题目');
              container.innerHTML = '<div class="no-problems-message">❌ 没有找到匹配的题目，请尝试其他筛选条件</div>';
            }
          } else {
            const errorMsg = (resp && resp.message) || '获取筛选题目失败';
            console.error('[exam] API返回失败:', errorMsg, resp);
            container.innerHTML = `<div class="error-message">❌ 筛选失败: ${errorMsg}</div>`;
          }
        } catch (apiError) {
          console.error('[exam] API请求异常:', apiError);
          // 如果后端返回了明确的错误信息（例如 400: 筛选功能需要登录用户），优先展示该信息
          const msg = (apiError && apiError.message) ? String(apiError.message) : '网络请求失败，请检查服务器连接';
          container.innerHTML = `<div class="error-message">❌ ${msg}</div>`;
        }
      } else if (type === 'setProblems' && Array.isArray(payload?.problems)) {
        const list = payload.problems;
        api.setCurrentProblems(list);
        api.renderProblems(list, list.length);
      }
    } catch (e) {
      console.error('[exam] 处理父页面消息失败:', e);
    }
  });
