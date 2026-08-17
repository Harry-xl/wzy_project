/**
 * API 通信模块
 * 处理与后端的所有HTTP请求
 */

class ApiClient {
    constructor(baseUrl = 'http://127.0.0.1:3001') {
        this.baseUrl = baseUrl;
    }

    /**
     * 通用API请求方法
     * @param {string} endpoint - API端点
     * @param {Object} data - 请求数据
     * @param {string} method - HTTP方法
     * @returns {Promise} API响应
     */
    async request(endpoint, data = null, method = 'POST') {
        try {
            const config = {
                method,
                headers: {}
            };

            // 仅在非 GET 请求时设置 JSON Content-Type，避免 GET 触发不必要的 CORS 预检
            if (method !== 'GET') {
                config.headers['Content-Type'] = 'application/json';
            }

            // 注意：不在通用请求中附加 Authorization 头，避免登录/注册时触发额外预检导致失败
            // 如需鉴权，请在具体需要的 API（如流式聊天）单独附加

            if (data && method !== 'GET') {
                config.body = JSON.stringify(data);
            }

            const response = await fetch(`${this.baseUrl}${endpoint}`, config);

            if (!response.ok) {
                // 尝试解析错误消息，若失败则抛出通用错误
                let message = '请求失败';
                try {
                    const errorData = await response.json();
                    message = errorData.message || message;
                } catch (_) {}
                throw new Error(message);
            }

            return await response.json();
        } catch (error) {
            console.error('API请求错误:', error);
            throw error;
        }
    }

    /**
     * 用户登录
     * @param {string} username - 用户名
     * @param {string} password - 密码
     * @returns {Promise} 登录结果
     */
    async login(email, password) {
        // 后端需要 email, password
        return await this.request('/api/login', { email, password });
    }

    /**
     * 用户注册
     * @param {string} name - 姓名
     * @param {string} username - 用户名
     * @param {string} password - 密码
     * @returns {Promise} 注册结果
     */
    async register(name, email, password) {
        // 后端注册在 /api/signup
        return await this.request('/api/signup', { name, email, password });
    }

    /**
     * 修改密码
     * @param {string} username - 用户名
     * @param {string} oldpwd - 原密码
     * @param {string} newpwd - 新密码
     * @returns {Promise} 修改结果
     */
    async changePassword(username, oldpwd, newpwd) {
        return await this.request('/api/change_password', { username, oldpwd, newpwd });
    }

    /**
     * 发起聊天（流式响应）
     * @param {string} message - 消息内容
     * @param {string} username - 用户名
     * @param {string} chatId - 对话ID
     * @param {string} systemPrompt - 系统提示词（可选）
     * @param {AbortSignal} signal - 中断信号
     * @returns {Response} 流式响应
     */
    async chatStream(message, username, chatId, systemPrompt = null, signal = null, options = {}) {
        const requestData = {
            message,
            username,
            chat_id: chatId
        };

        if (systemPrompt !== null) {
            requestData.system_prompt = systemPrompt;
        }

        // 知识范围切换: "system" | "personal"
        if (options.knowledge_scope) {
            requestData.knowledge_scope = options.knowledge_scope;
        }
        if (options.user_id) {
            requestData.user_id = options.user_id;
        }

        const config = {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        };

        // 注意：不再添加 Authorization 头，因为后端不使用它，
        // 且携带该头会触发 CORS 预检，与 Access-Control-Allow-Origin: * 冲突

        if (signal) {
            config.signal = signal;
        }

        return await fetch(`${this.baseUrl}/api/chat`, config);
    }

    /**
     * 清除对话记忆
     * @param {string} username - 用户名
     * @param {string} chatId - 对话ID
     * @returns {Promise} 清除结果
     */
    async clearMemory(username, chatId) {
        return await this.request('/api/clear_memory', { username, chat_id: chatId });
    }

    /**
     * 设置系统提示词
     * @param {string} username - 用户名
     * @param {string} chatId - 对话ID
     * @param {string} systemPrompt - 系统提示词（传null则使用默认值）
     * @returns {Promise} 设置结果
     */
    async setSystemPrompt(username, chatId, systemPrompt) {
        return await this.request('/api/set_system_prompt', {
            username,
            chat_id: chatId,
            system_prompt: systemPrompt
        });
    }

    /**
     * 获取当前系统提示词
     * @param {string} username - 用户名
     * @param {string} chatId - 对话ID
     * @returns {Promise} 包含系统提示词的响应
     */
    async getSystemPrompt(username, chatId) {
        return await this.request('/api/get_system_prompt', {
            username,
            chat_id: chatId
        });
    }

    /**
     * 获取服务状态
     * @returns {Promise} 服务状态
     */
    async getHealth() {
        return await this.request('/health', null, 'GET');
    }

    /**
     * 获取用户的长期记忆
     * @param {number} limit - 返回记忆数量限制
     * @returns {Promise} 长期记忆列表
     */
    async getLongTermMemories(limit = 10) {
        return await this.request(`/api/memory/long-term?limit=${limit}`, null, 'GET');
    }

    /**
     * 更新特定的长期记忆
     * @param {string} memoryId - 记忆ID
     * @param {string} text - 新的记忆内容
     * @param {Object} metadata - 可选的元数据
     * @returns {Promise} 更新结果
     */
    async updateLongTermMemory(memoryId, text, metadata = null) {
        const data = { text };
        if (metadata) {
            data.metadata = metadata;
        }
        return await this.request(`/api/memory/long-term/${memoryId}`, data, 'PUT');
    }

    /**
     * 删除特定的长期记忆
     * @param {string} memoryId - 记忆ID
     * @returns {Promise} 删除结果
     */
    async deleteLongTermMemory(memoryId) {
        return await this.request(`/api/memory/long-term/${memoryId}`, null, 'DELETE');
    }

    /**
     * 清除所有长期记忆
     * @returns {Promise} 清除结果
     */
    async clearLongTermMemories() {
        return await this.request('/api/memory/long-term', null, 'DELETE');
    }
    // 获取题目（支持游客随机/用户个性化）
    /**
     * 获取题目列表
     * @param {number|null} userId - 用户ID（null 或 0 表示游客，返回随机题）
     * @param {number} count - 题目数量（默认5）
     * @param {number|null} staleDays - 个性化推荐中的“久未做”阈值天数（>0 生效，默认后端使用30）
     * @returns {Promise<{success:boolean, problems?:Array, message?:string}>}
     */
    async getProblems(userId = null, count = 5, staleDays = null) {
        console.log('[api.getProblems] userId=', userId, ' count=', count, ' staleDays=', staleDays);
        const qs = new URLSearchParams();
        qs.set('count', count);
        if (userId) qs.set('user_id', userId);
        if (typeof staleDays === 'number' && staleDays > 0) qs.set('stale_days', String(staleDays));
        const url = `/api/problems?${qs.toString()}`;
        console.log('[api.getProblems] 请求URL =', `${this.baseUrl}${url}`);
        return await this.request(url, null, 'GET');
    }

    /**
     * 根据过滤条件获取题目列表
     * @param {number} userId 登录用户ID
     * @param {number} count 数量
     * @param {{knowledgePoints?:string[], difficulties?:string[], staleDays?:number}} opts 过滤条件
     * @returns {Promise<{success:boolean,problems?:Array}>}
     */
    async getProblemsByFilter(userId, count = 5, opts = {}) {
        const qs = new URLSearchParams();
        qs.set('count', String(count));
        if (userId) qs.set('user_id', String(userId));
        if (opts && Array.isArray(opts.knowledgePoints) && opts.knowledgePoints.length > 0) {
            qs.set('knowledge_points', opts.knowledgePoints.join(','));
        }
        if (opts && Array.isArray(opts.difficulties) && opts.difficulties.length > 0) {
            qs.set('difficulties', opts.difficulties.join(','));
        }
        if (opts && typeof opts.staleDays === 'number' && opts.staleDays > 0) {
            qs.set('stale_days', String(opts.staleDays));
        }
        const url = `/api/problems/filter?${qs.toString()}`;
        console.log('[api.getProblemsByFilter] 请求URL =', `${this.baseUrl}${url}`);
        return await this.request(url, null, 'GET');
    }
    async getKnowledgePoints() {
        return await this.request('/api/knowledge_points', null, 'GET');
    }
    // 提交答案
    async submitAnswer(userId, problemId, userAnswer) {
        return await this.request('/api/submit_answer', {
            user_id: userId,
            problem_id: problemId,
            user_answer: userAnswer
        });
    }
    // 获取用户能力画像
    async getUserProfile(userId) {
        return await this.request(`/api/user_profile/${userId}`, null, 'GET');
    }
    /**
     * 获取用户实力趋势（mini 折线图数据源）
     * @param {number} userId
     * @returns {Promise<{success:boolean, trend?: Array<{t:string, value:number}>, message?:string}>>}
     */
    async getUserStrengthTrend(userId) {
        return await this.request(`/api/user_strength_trend/${userId}`, null, 'GET');
    }
    /**
     * 获取用户错题列表
     * @param {number} userId - 用户ID
     * @param {number} [limit=50] - 返回数量上限
     * @param {number} [offset=0] - 偏移量（分页）
     * @returns {Promise<{success:boolean, items?:Array}>}
     */
    async getWrongAnswers(userId, limit = 50, offset = 0, sortBy = 'time') {
        const qs = new URLSearchParams();
        qs.set('limit', String(limit));
        if (offset && offset > 0) qs.set('offset', String(offset));
        if (sortBy) qs.set('sort_by', String(sortBy));
        return await this.request(`/api/wrong_answers/${userId}?${qs.toString()}`, null, 'GET');
    }

    async getWrongRedoProblems(userId, opts = {}) {
        const qs = new URLSearchParams();
        const mode = opts.mode || 'time';
        const count = opts.count || 10;
        const knowledgePoint = opts.knowledgePoint || '';
        qs.set('mode', String(mode));
        qs.set('count', String(count));
        if (knowledgePoint) qs.set('knowledge_point', String(knowledgePoint));
        return await this.request(`/api/wrong_redo/${userId}?${qs.toString()}`, null, 'GET');
    }

    /**
     * 生成单题 AI 讲解
     * @param {{problem_text:string, knowledge_point?:string, difficulty?:string, user_answer?:string, correct_answer?:string}} payload - 讲解参数
     * @returns {Promise<{success:boolean, explanation?:string, message?:string}>}
     */
    /**
     * 以流式方式请求题目讲解（ReadableStream）
     * @param {{problem_text:string, knowledge_point?:string, difficulty?:string, user_answer?:string, correct_answer?:string}} payload
     * @param {AbortSignal} signal - 用于中止请求的信号
     * @returns {Promise<ReadableStream<Uint8Array>|null>} 返回可读流；若失败返回 null
     */
    async explainProblemStream(payload, signal = null) {
        const url = `${this.baseUrl}/api/explain/stream`;
        try {
            const fetchOptions = {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            };
            
            // 如果提供了AbortSignal，添加到fetch选项中
            if (signal) {
                fetchOptions.signal = signal;
            }
            
            const resp = await fetch(url, fetchOptions);
            if (!resp.ok) {
                console.error('[explainProblemStream] HTTP 状态异常:', resp.status, resp.statusText);
                return null;
            }
            if (!resp.body || typeof resp.body.getReader !== 'function') {
                console.error('[explainProblemStream] 响应没有可读流 body');
                return null;
            }
            return resp.body;
        } catch (e) {
            console.error('[explainProblemStream] 请求异常:', e);
            return null;
        }
    }
}

// 创建全局API客户端实例
const apiClient = new ApiClient();

// 导出API客户端（用于模块化使用）
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ApiClient;
}
