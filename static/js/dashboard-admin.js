/**
 * StarPal — 管理后台模块
 */
(function () {
  const DS = window.__DS;
  if (!DS) return;
  const { $, escapeHtml } = DS;

  let adminCurrentPage = 1, adminTotalPages = 1, adminPageSize = 10, adminEditingId = null, adminPreviewData = null;

  function bindEvents() {
    $('#adminSearchBtn')?.addEventListener('click', () => { adminCurrentPage = 1; loadProblems(); });
    $('#adminAddBtn')?.addEventListener('click', () => openModal());
    $('#adminUploadArea')?.addEventListener('click', () => $('#adminFileInput')?.click());
    $('#adminFileInput')?.addEventListener('change', function () { if (this.files[0]) processFile(this.files[0]); });
    $('#adminConfirmImport')?.addEventListener('click', confirmImport);
    $('#adminCancelImport')?.addEventListener('click', cancelImport);
    $('#adminModalCancel')?.addEventListener('click', closeModal);
    $('#adminProblemForm')?.addEventListener('submit', function (e) { e.preventDefault(); saveProblem(); });
    $('#adminEditModal')?.addEventListener('click', function (e) { if (e.target === this) closeModal(); });

    const ua = $('#adminUploadArea');
    if (ua) {
      ua.addEventListener('dragover', e => { e.preventDefault(); ua.classList.add('dragover'); });
      ua.addEventListener('dragleave', () => ua.classList.remove('dragover'));
      ua.addEventListener('drop', e => { e.preventDefault(); ua.classList.remove('dragover'); if (e.dataTransfer.files[0]) processFile(e.dataTransfer.files[0]); });
    }
  }

  async function loadProblems(page = 1) {
    adminCurrentPage = page;
    const params = { page, page_size: adminPageSize };
    const search = $('#adminSearch')?.value?.trim(); if (search) params.search = search;
    const diff = $('#adminDiffFilter')?.value; if (diff) params.difficulty = diff;
    const kp = $('#adminKpFilter')?.value; if (kp) params.knowledge_point = kp;
    try {
      const resp = await apiClient.request('/api/admin/problems', params, 'GET');
      if (!resp?.success) { $('#adminTableBody').innerHTML = '<tr><td colspan="7" style="text-align:center;">加载失败</td></tr>'; return; }
      adminTotalPages = resp.total_pages || 1;
      renderTable(resp.problems || []);
      renderPagination();
    } catch (_) { $('#adminTableBody').innerHTML = '<tr><td colspan="7" style="text-align:center;">加载失败</td></tr>'; }
  }

  function renderTable(problems) {
    if (!problems.length) { $('#adminTableBody').innerHTML = '<tr><td colspan="7" style="text-align:center;padding:32px;color:var(--color-text-muted);">暂无数据</td></tr>'; return; }
    $('#adminTableBody').innerHTML = problems.map(p => `
      <tr>
        <td>${escapeHtml(p.problem_num || '')}</td>
        <td title="${escapeHtml(p.problem || '')}">${escapeHtml((p.problem || '').substring(0, 60))}${(p.problem || '').length > 60 ? '...' : ''}</td>
        <td>${escapeHtml((p.answer || '').substring(0, 20))}</td>
        <td><span class="badge ${p.difficulty === '简单' ? 'badge-success' : p.difficulty === '困难' ? 'badge-danger' : 'badge-warning'}">${p.difficulty}</span></td>
        <td>${escapeHtml(p.knowledge_point || '')}</td>
        <td style="font-size:11px;color:var(--color-text-muted);">${p.created_at ? new Date(p.created_at).toLocaleDateString('zh-CN') : '-'}</td>
        <td>
          <button class="btn btn-outline btn-sm" onclick="window.__DS.Admin._edit(${p.problem_id})"><i class="ri-edit-line"></i></button>
          <button class="btn btn-danger btn-sm" onclick="window.__DS.Admin._delete(${p.problem_id})"><i class="ri-delete-bin-line"></i></button>
        </td>
      </tr>`).join('');
  }

  function renderPagination() {
    const el = $('#adminPagination'); if (adminTotalPages <= 1) { el.innerHTML = ''; return; }
    let html = '';
    if (adminCurrentPage > 1) html += `<button onclick="window.__DS.Admin._goPage(${adminCurrentPage - 1})">‹</button>`;
    const start = Math.max(1, adminCurrentPage - 2), end = Math.min(adminTotalPages, adminCurrentPage + 2);
    for (let i = start; i <= end; i++) html += `<button class="${i === adminCurrentPage ? 'active' : ''}" onclick="window.__DS.Admin._goPage(${i})">${i}</button>`;
    if (adminCurrentPage < adminTotalPages) html += `<button onclick="window.__DS.Admin._goPage(${adminCurrentPage + 1})">›</button>`;
    el.innerHTML = html;
  }

  function openModal(problemId) {
    adminEditingId = problemId || null;
    $('#adminModalTitle').textContent = problemId ? '编辑题目' : '添加题目';
    if (problemId) {
      apiClient.request('/api/admin/problems', { page: 1, page_size: 1000 }, 'GET').then(resp => {
        const p = (resp?.problems || []).find(p => p.problem_id === problemId);
        if (p) {
          $('#adminFormNum').value = p.problem_num || ''; $('#adminFormProblem').value = p.problem || '';
          $('#adminFormAnswer').value = p.answer || ''; $('#adminFormDifficulty').value = p.difficulty || '简单';
          $('#adminFormKp').value = p.knowledge_point || '';
        }
      }).catch(() => { });
    } else {
      ['adminFormNum', 'adminFormProblem', 'adminFormAnswer', 'adminFormKp'].forEach(id => { $('#' + id).value = ''; });
      $('#adminFormDifficulty').value = '简单';
    }
    $('#adminEditModal').classList.remove('hidden');
  }
  function closeModal() { $('#adminEditModal').classList.add('hidden'); adminEditingId = null; }

  async function saveProblem() {
    const data = {
      problem_num: $('#adminFormNum').value.trim(), problem: $('#adminFormProblem').value.trim(),
      answer: $('#adminFormAnswer').value.trim(), difficulty: $('#adminFormDifficulty').value,
      knowledge_point: $('#adminFormKp').value.trim()
    };
    if (!data.problem_num || !data.problem || !data.answer || !data.knowledge_point) { Utils.showToast('请填写所有字段'); return; }
    try {
      const url = adminEditingId ? `/api/admin/problems/${adminEditingId}` : '/api/admin/problems';
      const resp = await apiClient.request(url, data, adminEditingId ? 'PUT' : 'POST');
      if (resp?.success) { closeModal(); loadProblems(adminCurrentPage); loadStats(); Utils.showToast(adminEditingId ? '更新成功' : '创建成功'); }
      else Utils.showToast(resp?.message || '保存失败');
    } catch (_) { Utils.showToast('保存失败'); }
  }

  async function loadStats() {
    try {
      const resp = await apiClient.request('/api/admin/stats', null, 'GET');
      if (!resp?.success) return;
      const s = resp.stats;
      $('#statTotal').textContent = s.total_problems || 0;
      $('#statEasy').textContent = s.difficulty_stats?.['简单'] || 0;
      $('#statMedium').textContent = s.difficulty_stats?.['中等'] || 0;
      $('#statHard').textContent = s.difficulty_stats?.['困难'] || 0;
      if (s.knowledge_stats) {
        $('#adminKpStats').innerHTML = Object.entries(s.knowledge_stats).slice(0, 10).map(([k, v]) =>
          `<span class="badge badge-primary" style="margin:2px 4px;">${escapeHtml(k)}: ${v}</span>`).join('');
      }
      if (s.recent_problems) {
        $('#adminRecentProblems').innerHTML = s.recent_problems.map(p =>
          `<div style="font-size:12px;padding:4px 0;border-bottom:1px solid var(--color-border);">${escapeHtml(p.problem_num)}: ${escapeHtml((p.problem || '').substring(0, 50))}...</div>`).join('');
      }
    } catch (_) { }
  }

  async function loadKpOptions() {
    try {
      const resp = await apiClient.request('/api/admin/knowledge-points', null, 'GET');
      if (resp?.success && resp.knowledge_points) {
        $('#adminKpFilter').innerHTML = '<option value="">所有知识点</option>' + resp.knowledge_points.map(kp => `<option value="${escapeHtml(kp)}">${escapeHtml(kp)}</option>`).join('');
      }
    } catch (_) { }
  }

  async function processFile(file) {
    const text = await file.text(); const ext = file.name.split('.').pop().toLowerCase();
    let data;
    try { if (ext === 'json') data = JSON.parse(text); else if (ext === 'csv') data = parseCSV(text); }
    catch (e) { Utils.showToast('文件解析失败：' + e.message); return; }
    if (!Array.isArray(data) || !data.length) { Utils.showToast('无有效数据'); return; }
    adminPreviewData = data;
    const preview = data.slice(0, 5);
    $('#adminPreviewContent').innerHTML = `<p style="margin-bottom:8px;">预览前 ${Math.min(5, data.length)} / 共 ${data.length} 道：</p>
      <table class="admin-table"><thead><tr><th>编号</th><th>题目</th><th>答案</th><th>难度</th><th>知识点</th></tr></thead><tbody>
      ${preview.map(p => `<tr><td>${escapeHtml(p.problem_num)}</td><td>${escapeHtml((p.problem || '').substring(0, 80))}</td><td>${escapeHtml((p.answer || '').substring(0, 30))}</td><td>${escapeHtml(p.difficulty)}</td><td>${escapeHtml(p.knowledge_point)}</td></tr>`).join('')}
      </tbody></table>${data.length > 5 ? `<p style="margin-top:8px;color:var(--color-text-muted);">...还有 ${data.length - 5} 道未显示</p>` : ''}`;
    $('#adminPreviewSection').style.display = '';
  }

  function parseCSV(text) {
    const lines = text.trim().split('\n'); if (lines.length < 2) throw new Error('CSV 至少需要标题行和一行数据');
    const headers = lines[0].split(',').map(h => h.trim().replace(/"/g, ''));
    return lines.slice(1).map(line => {
      const vals = []; let cur = '', inQ = false;
      for (const ch of line) { if (ch === '"') { inQ = !inQ; continue; } if (ch === ',' && !inQ) { vals.push(cur.trim()); cur = ''; continue; } cur += ch; }
      vals.push(cur.trim()); const obj = {}; headers.forEach((h, i) => { obj[h] = vals[i] || ''; }); return obj;
    });
  }

  async function confirmImport() {
    if (!adminPreviewData?.length) return;
    try {
      const resp = await apiClient.request('/api/admin/import-problems', { problems: adminPreviewData }, 'POST');
      if (resp?.success) { Utils.showToast(`导入成功 ${resp.imported_count} 道`); cancelImport(); loadProblems(); loadStats(); }
      else Utils.showToast(resp?.message || '导入失败');
    } catch (_) { Utils.showToast('导入失败'); }
  }
  function cancelImport() { adminPreviewData = null; $('#adminPreviewSection').style.display = 'none'; $('#adminFileInput').value = ''; }

  bindEvents();

  DS.Admin = {
    loadProblems, loadStats, loadKpOptions,
    _goPage: (p) => loadProblems(p),
    _edit: (id) => openModal(id),
    _delete: async (id) => {
      if (!confirm('确定删除？此操作不可恢复。')) return;
      try { await apiClient.request(`/api/admin/problems/${id}`, null, 'DELETE'); loadProblems(adminCurrentPage); loadStats(); } catch (_) { }
    }
  };
})();
