/**
 * 题目管理系统前端逻辑
 * 负责批量导入、题目管理、统计信息等功能
 * Updated: 2025-01-13
 */

(function() {
    'use strict';

    // DOM 元素
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');
    const statusMessage = document.getElementById('statusMessage');
    const previewSection = document.getElementById('previewSection');
    const previewContent = document.getElementById('previewContent');
    const confirmImportBtn = document.getElementById('confirmImport');
    const cancelImportBtn = document.getElementById('cancelImport');
    const backToDashboardBtn = document.getElementById('backToDashboard');
    
    // 题目管理相关元素
    const searchInput = document.getElementById('searchInput');
    const difficultyFilter = document.getElementById('difficultyFilter');
    const knowledgeFilter = document.getElementById('knowledgeFilter');
    const searchBtn = document.getElementById('searchBtn');
    const addProblemBtn = document.getElementById('addProblemBtn');
    const problemsTableBody = document.getElementById('problemsTableBody');
    const pagination = document.getElementById('pagination');
    
    // 模态框相关元素
    const editModal = document.getElementById('editModal');
    const modalTitle = document.getElementById('modalTitle');
    const closeModalBtn = document.getElementById('closeModal');
    const problemForm = document.getElementById('problemForm');
    const saveProblemBtn = document.getElementById('saveProblem');
    const cancelEditBtn = document.getElementById('cancelEdit');

    // 全局变量
    let currentPage = 1;
    let pageSize = 10;
    let totalPages = 1;
    let currentProblems = [];
    let previewData = null;
    let editingProblemId = null;
    let knowledgePoints = [];

    // API 实例
    const api = new ApiClient();

    /**
     * 初始化页面
     */
    function init() {
        // 检查登录状态（可选，根据需求决定是否需要登录）
        const userName = storageManager.getCurrentUserName();
        if (userName) {
            document.getElementById('adminName').textContent = userName;
        }

        // 绑定事件
        bindEvents();
        
        // 加载初始数据
        loadProblems();
        loadKnowledgePoints();
        loadStats();
    }

    /**
     * 绑定事件监听器
     */
    function bindEvents() {
        // 标签页切换
        tabBtns.forEach(btn => {
            btn.addEventListener('click', () => switchTab(btn.dataset.tab));
        });

        // 返回仪表盘
        backToDashboardBtn.addEventListener('click', () => {
            window.location.href = 'dashboard.html';
        });

        // 文件上传相关事件
        uploadArea.addEventListener('dragover', handleDragOver);
        uploadArea.addEventListener('dragleave', handleDragLeave);
        uploadArea.addEventListener('drop', handleDrop);
        fileInput.addEventListener('change', handleFileSelect);
        
        // 导入确认/取消
        confirmImportBtn.addEventListener('click', confirmImport);
        cancelImportBtn.addEventListener('click', cancelImport);

        // 搜索和筛选
        searchBtn.addEventListener('click', searchProblems);
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') searchProblems();
        });
        difficultyFilter.addEventListener('change', searchProblems);
        knowledgeFilter.addEventListener('change', searchProblems);

        // 添加题目
        addProblemBtn.addEventListener('click', () => openEditModal());

        // 模态框事件
        closeModalBtn.addEventListener('click', closeEditModal);
        cancelEditBtn.addEventListener('click', closeEditModal);
        saveProblemBtn.addEventListener('click', saveProblem);
        
        // 阻止表单默认提交
        problemForm.addEventListener('submit', (e) => {
            e.preventDefault();
            saveProblem();
        });
        
        // 点击模态框外部关闭
        editModal.addEventListener('click', (e) => {
            if (e.target === editModal) closeEditModal();
        });
    }

    /**
     * 切换标签页
     */
    function switchTab(tabName) {
        // 更新按钮状态
        tabBtns.forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tabName);
        });

        // 更新内容显示
        tabContents.forEach(content => {
            content.classList.toggle('active', content.id === `${tabName}-tab`);
        });

        // 根据标签页加载相应数据
        switch(tabName) {
            case 'manage':
                loadProblems();
                break;
            case 'stats':
                loadStats();
                break;
        }
    }

    /**
     * 处理拖拽悬停
     */
    function handleDragOver(e) {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    }

    /**
     * 处理拖拽离开
     */
    function handleDragLeave(e) {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
    }

    /**
     * 处理文件拖拽放置
     */
    function handleDrop(e) {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            processFile(files[0]);
        }
    }

    /**
     * 处理文件选择
     */
    function handleFileSelect(e) {
        const files = e.target.files;
        if (files.length > 0) {
            processFile(files[0]);
        }
    }

    /**
     * 处理上传的文件
     */
    async function processFile(file) {
        const fileName = file.name.toLowerCase();
        
        if (!fileName.endsWith('.json') && !fileName.endsWith('.csv')) {
            showStatus('只支持 JSON 和 CSV 格式的文件', 'error');
            return;
        }

        try {
            showStatus('正在读取文件...', 'warning');
            
            const text = await readFileAsText(file);
            let data;

            if (fileName.endsWith('.json')) {
                data = parseJSON(text);
            } else {
                data = parseCSV(text);
            }

            if (data && data.length > 0) {
                previewData = data;
                showPreview(data);
                showStatus(`成功解析 ${data.length} 道题目`, 'success');
            } else {
                showStatus('文件中没有找到有效的题目数据', 'error');
            }
        } catch (error) {
            console.error('文件处理错误:', error);
            showStatus(`文件处理失败: ${error.message}`, 'error');
        }
    }

    /**
     * 读取文件内容
     */
    function readFileAsText(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = e => resolve(e.target.result);
            reader.onerror = e => reject(new Error('文件读取失败'));
            reader.readAsText(file, 'UTF-8');
        });
    }

    /**
     * 解析 JSON 格式
     */
    function parseJSON(text) {
        try {
            const data = JSON.parse(text);
            if (!Array.isArray(data)) {
                throw new Error('JSON 文件应该包含一个数组');
            }
            return validateProblems(data);
        } catch (error) {
            throw new Error(`JSON 解析失败: ${error.message}`);
        }
    }

    /**
     * 解析 CSV 格式
     */
    function parseCSV(text) {
        const lines = text.trim().split('\n');
        if (lines.length < 2) {
            throw new Error('CSV 文件至少需要包含标题行和一行数据');
        }

        const headers = lines[0].split(',').map(h => h.trim().replace(/"/g, ''));
        const requiredHeaders = ['problem_num', 'problem', 'answer', 'difficulty', 'knowledge_point'];
        
        // 检查必需的列
        for (const header of requiredHeaders) {
            if (!headers.includes(header)) {
                throw new Error(`CSV 文件缺少必需的列: ${header}`);
            }
        }

        const data = [];
        for (let i = 1; i < lines.length; i++) {
            const values = parseCSVLine(lines[i]);
            if (values.length !== headers.length) {
                console.warn(`第 ${i + 1} 行数据列数不匹配，跳过`);
                continue;
            }

            const problem = {};
            headers.forEach((header, index) => {
                problem[header] = values[index];
            });
            data.push(problem);
        }

        return validateProblems(data);
    }

    /**
     * 解析 CSV 行（处理引号内的逗号）
     */
    function parseCSVLine(line) {
        const result = [];
        let current = '';
        let inQuotes = false;
        
        for (let i = 0; i < line.length; i++) {
            const char = line[i];
            
            if (char === '"') {
                inQuotes = !inQuotes;
            } else if (char === ',' && !inQuotes) {
                result.push(current.trim());
                current = '';
            } else {
                current += char;
            }
        }
        
        result.push(current.trim());
        return result;
    }

    /**
     * 验证题目数据
     */
    function validateProblems(problems) {
        const validProblems = [];
        const errors = [];

        problems.forEach((problem, index) => {
            const lineNum = index + 1;
            
            // 检查必需字段
            if (!problem.problem_num || !problem.problem || !problem.answer || 
                !problem.difficulty || !problem.knowledge_point) {
                errors.push(`第 ${lineNum} 行: 缺少必需字段`);
                return;
            }

            // 检查难度值
            if (!['简单', '中等', '困难'].includes(problem.difficulty)) {
                errors.push(`第 ${lineNum} 行: 难度值无效 (${problem.difficulty})`);
                return;
            }

            validProblems.push({
                problem_num: problem.problem_num.toString().trim(),
                problem: problem.problem.toString().trim(),
                answer: problem.answer.toString().trim(),
                difficulty: problem.difficulty.toString().trim(),
                knowledge_point: problem.knowledge_point.toString().trim()
            });
        });

        if (errors.length > 0) {
            throw new Error(`数据验证失败:\n${errors.join('\n')}`);
        }

        return validProblems;
    }

    /**
     * 显示预览
     */
    function showPreview(data) {
        const maxPreview = 5; // 最多预览5条
        const previewItems = data.slice(0, maxPreview);
        
        let html = `<p>将导入 ${data.length} 道题目，预览前 ${Math.min(maxPreview, data.length)} 道：</p>`;
        html += '<table class="problems-table">';
        html += '<thead><tr><th>编号</th><th>题目</th><th>答案</th><th>难度</th><th>知识点</th></tr></thead>';
        html += '<tbody>';
        
        previewItems.forEach(problem => {
            html += `<tr>
                <td>${escapeHtml(problem.problem_num)}</td>
                <td>${escapeHtml(problem.problem.substring(0, 100))}${problem.problem.length > 100 ? '...' : ''}</td>
                <td>${escapeHtml(problem.answer.substring(0, 50))}${problem.answer.length > 50 ? '...' : ''}</td>
                <td><span class="difficulty-badge difficulty-${problem.difficulty}">${problem.difficulty}</span></td>
                <td>${escapeHtml(problem.knowledge_point)}</td>
            </tr>`;
        });
        
        html += '</tbody></table>';
        
        if (data.length > maxPreview) {
            html += `<p>...还有 ${data.length - maxPreview} 道题目未显示</p>`;
        }
        
        previewContent.innerHTML = html;
        previewSection.style.display = 'block';
    }

    /**
     * 确认导入
     */
    async function confirmImport() {
        if (!previewData || previewData.length === 0) {
            showStatus('没有可导入的数据', 'error');
            return;
        }

        try {
            showStatus('正在导入题目...', 'warning');
            confirmImportBtn.disabled = true;
            
            const response = await api.request('/api/admin/import-problems', {
                problems: previewData
            }, 'POST');

            if (response.success) {
                showStatus(`成功导入 ${response.imported_count} 道题目`, 'success');
                cancelImport();
                loadProblems(); // 刷新题目列表
                loadStats(); // 刷新统计信息
            } else {
                showStatus(`导入失败: ${response.message}`, 'error');
            }
        } catch (error) {
            console.error('导入错误:', error);
            showStatus(`导入失败: ${error.message}`, 'error');
        } finally {
            confirmImportBtn.disabled = false;
        }
    }

    /**
     * 取消导入
     */
    function cancelImport() {
        previewData = null;
        previewSection.style.display = 'none';
        fileInput.value = '';
        hideStatus();
    }

    /**
     * 加载题目列表
     */
    async function loadProblems(page = 1) {
        try {
            const params = {
                page: page,
                page_size: pageSize
            };

            // 添加搜索和筛选条件
            const searchTerm = searchInput?.value?.trim();
            if (searchTerm) params.search = searchTerm;
            
            const difficulty = difficultyFilter?.value;
            if (difficulty) params.difficulty = difficulty;
            
            const knowledge = knowledgeFilter?.value;
            if (knowledge) params.knowledge_point = knowledge;

            const response = await api.request('/api/admin/problems', params, 'GET');
            
            if (response.success) {
                currentProblems = response.problems || [];
                totalPages = response.total_pages || 1;
                currentPage = page;
                
                renderProblemsTable();
                renderPagination();
            } else {
                showStatus(`加载题目失败: ${response.message}`, 'error');
            }
        } catch (error) {
            console.error('加载题目错误:', error);
            showStatus(`加载题目失败: ${error.message}`, 'error');
        }
    }

    /**
     * 渲染题目表格
     */
    function renderProblemsTable() {
        if (!currentProblems || currentProblems.length === 0) {
            problemsTableBody.innerHTML = '<tr><td colspan="7" style="text-align: center;">暂无题目数据</td></tr>';
            return;
        }

        let html = '';
        currentProblems.forEach(problem => {
            html += `<tr>
                <td>${escapeHtml(problem.problem_num || problem.problem_id)}</td>
                <td title="${escapeHtml(problem.problem)}">${escapeHtml(problem.problem.substring(0, 80))}${problem.problem.length > 80 ? '...' : ''}</td>
                <td title="${escapeHtml(problem.answer)}">${escapeHtml(problem.answer.substring(0, 30))}${problem.answer.length > 30 ? '...' : ''}</td>
                <td><span class="difficulty-badge difficulty-${problem.difficulty}">${problem.difficulty}</span></td>
                <td>${escapeHtml(problem.knowledge_point)}</td>
                <td>${formatDate(problem.created_at)}</td>
                <td>
                    <button class="action-btn edit-btn" onclick="adminManager.editProblem(${problem.problem_id})">编辑</button>
                    <button class="action-btn delete-btn" onclick="adminManager.deleteProblem(${problem.problem_id})">删除</button>
                </td>
            </tr>`;
        });
        
        problemsTableBody.innerHTML = html;
    }

    /**
     * 渲染分页
     */
    function renderPagination() {
        if (totalPages <= 1) {
            pagination.innerHTML = '';
            return;
        }

        let html = '';
        
        // 上一页
        if (currentPage > 1) {
            html += `<button class="page-btn" onclick="adminManager.loadProblems(${currentPage - 1})">上一页</button>`;
        }

        // 页码
        const startPage = Math.max(1, currentPage - 2);
        const endPage = Math.min(totalPages, currentPage + 2);
        
        for (let i = startPage; i <= endPage; i++) {
            const activeClass = i === currentPage ? 'active' : '';
            html += `<button class="page-btn ${activeClass}" onclick="adminManager.loadProblems(${i})">${i}</button>`;
        }

        // 下一页
        if (currentPage < totalPages) {
            html += `<button class="page-btn" onclick="adminManager.loadProblems(${currentPage + 1})">下一页</button>`;
        }

        pagination.innerHTML = html;
    }

    /**
     * 搜索题目
     */
    function searchProblems() {
        loadProblems(1); // 重置到第一页
    }

    /**
     * 加载知识点列表
     */
    async function loadKnowledgePoints() {
        try {
            const response = await api.request('/api/admin/knowledge-points', null, 'GET');
            if (response.success && response.knowledge_points) {
                knowledgePoints = response.knowledge_points;
                
                // 更新知识点筛选下拉框
                let html = '<option value="">所有知识点</option>';
                knowledgePoints.forEach(kp => {
                    html += `<option value="${escapeHtml(kp)}">${escapeHtml(kp)}</option>`;
                });
                knowledgeFilter.innerHTML = html;
            }
        } catch (error) {
            console.error('加载知识点错误:', error);
        }
    }

    /**
     * 加载统计信息
     */
    async function loadStats() {
        try {
            const response = await api.request('/api/admin/stats', null, 'GET');
            if (response.success) {
                const stats = response.stats;
                
                // 更新总数
                document.getElementById('totalProblems').textContent = stats.total_problems || 0;
                
                // 更新难度分布
                document.getElementById('easyCount').textContent = stats.difficulty_stats?.简单 || 0;
                document.getElementById('mediumCount').textContent = stats.difficulty_stats?.中等 || 0;
                document.getElementById('hardCount').textContent = stats.difficulty_stats?.困难 || 0;
                
                // 更新知识点分布
                const knowledgeStatsEl = document.getElementById('knowledgeStats');
                if (stats.knowledge_stats) {
                    let html = '';
                    Object.entries(stats.knowledge_stats).slice(0, 10).forEach(([kp, count]) => {
                        html += `<div>${escapeHtml(kp)}: ${count}</div>`;
                    });
                    knowledgeStatsEl.innerHTML = html;
                }
                
                // 更新最近添加
                const recentProblemsEl = document.getElementById('recentProblems');
                if (stats.recent_problems) {
                    let html = '';
                    stats.recent_problems.forEach(problem => {
                        html += `<div title="${escapeHtml(problem.problem)}">${escapeHtml(problem.problem_num)}: ${escapeHtml(problem.problem.substring(0, 30))}...</div>`;
                    });
                    recentProblemsEl.innerHTML = html;
                }
            }
        } catch (error) {
            console.error('加载统计信息错误:', error);
        }
    }

    /**
     * 编辑题目
     */
    function editProblem(problemId) {
        const problem = currentProblems.find(p => p.problem_id === problemId);
        if (!problem) {
            showStatus('题目不存在', 'error');
            return;
        }
        
        openEditModal(problem);
    }

    /**
     * 删除题目
     */
    async function deleteProblem(problemId) {
        if (!confirm('确定要删除这道题目吗？此操作不可恢复。')) {
            return;
        }

        try {
            const response = await api.request(`/api/admin/problems/${problemId}`, null, 'DELETE');
            if (response.success) {
                showStatus('题目删除成功', 'success');
                loadProblems(currentPage);
                loadStats();
            } else {
                showStatus(`删除失败: ${response.message}`, 'error');
            }
        } catch (error) {
            console.error('删除题目错误:', error);
            showStatus(`删除失败: ${error.message}`, 'error');
        }
    }

    /**
     * 打开编辑模态框
     */
    function openEditModal(problem = null) {
        editingProblemId = problem ? problem.problem_id : null;
        modalTitle.textContent = problem ? '编辑题目' : '添加题目';
        
        if (problem) {
            document.getElementById('problemNum').value = problem.problem_num || '';
            document.getElementById('problemContent').value = problem.problem || '';
            document.getElementById('problemAnswer').value = problem.answer || '';
            document.getElementById('problemDifficulty').value = problem.difficulty || '简单';
            document.getElementById('problemKnowledge').value = problem.knowledge_point || '';
        } else {
            problemForm.reset();
        }
        
        editModal.style.display = 'block';
    }

    /**
     * 关闭编辑模态框
     */
    function closeEditModal() {
        editModal.style.display = 'none';
        editingProblemId = null;
        problemForm.reset();
    }

    /**
     * 保存题目
     */
    async function saveProblem() {
        const formData = new FormData(problemForm);
        const problemData = {
            problem_num: formData.get('problem_num'),
            problem: formData.get('problem'),
            answer: formData.get('answer'),
            difficulty: formData.get('difficulty'),
            knowledge_point: formData.get('knowledge_point')
        };

        // 验证数据
        for (const [key, value] of Object.entries(problemData)) {
            if (!value || !value.trim()) {
                showStatus(`请填写${getFieldName(key)}`, 'error');
                return;
            }
        }

        try {
            saveProblemBtn.disabled = true;
            
            const url = editingProblemId ? 
                `/api/admin/problems/${editingProblemId}` : 
                '/api/admin/problems';
            const method = editingProblemId ? 'PUT' : 'POST';
            
            const response = await api.request(url, problemData, method);
            
            if (response.success) {
                showStatus(editingProblemId ? '题目更新成功' : '题目添加成功', 'success');
                closeEditModal();
                loadProblems(currentPage);
                loadStats();
            } else {
                showStatus(`保存失败: ${response.message}`, 'error');
            }
        } catch (error) {
            console.error('保存题目错误:', error);
            showStatus(`保存失败: ${error.message}`, 'error');
        } finally {
            saveProblemBtn.disabled = false;
        }
    }

    /**
     * 获取字段中文名
     */
    function getFieldName(fieldName) {
        const fieldNames = {
            problem_num: '题目编号',
            problem: '题目内容',
            answer: '答案',
            difficulty: '难度',
            knowledge_point: '知识点'
        };
        return fieldNames[fieldName] || fieldName;
    }

    /**
     * 显示状态消息
     */
    function showStatus(message, type = 'info') {
        statusMessage.textContent = message;
        statusMessage.className = `status-message status-${type}`;
        statusMessage.style.display = 'block';
        
        // 3秒后自动隐藏成功消息
        if (type === 'success') {
            setTimeout(hideStatus, 3000);
        }
    }

    /**
     * 隐藏状态消息
     */
    function hideStatus() {
        statusMessage.style.display = 'none';
    }

    /**
     * HTML转义
     */
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * 格式化日期
     */
    function formatDate(dateString) {
        if (!dateString) return '-';
        const date = new Date(dateString);
        return date.toLocaleDateString('zh-CN') + ' ' + date.toLocaleTimeString('zh-CN', {hour: '2-digit', minute: '2-digit'});
    }

    // 全局暴露管理器对象，供HTML中的onclick使用
    window.adminManager = {
        loadProblems,
        editProblem,
        deleteProblem
    };

    // 页面加载完成后初始化
    document.addEventListener('DOMContentLoaded', init);

})();