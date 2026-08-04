/**
 * 本地存储管理模块
 * 提供用户数据和聊天记录的本地存储功能
 */

class StorageManager {
    constructor() {
        this.currentUser = this.getCurrentUser();
    }

    /**
     * 获取当前登录用户
     * @returns {string|null} 用户名
     */
    getCurrentUser() {
        return localStorage.getItem('currentUser');
    }

    /**
     * 设置当前登录用户
     * @param {string} username - 用户名
     * @param {string} name - 显示名称
     */
    setCurrentUser(username, name, userId = null) {
        localStorage.setItem('currentUser', username);
        localStorage.setItem('currentName', name);
        if (userId !== null && userId !== undefined) {
            localStorage.setItem('currentUserId', String(userId));
        }
        this.currentUser = username;
    }

    /**
     * 清除当前用户信息
     */
    clearCurrentUser() {
        localStorage.removeItem('currentUser');
        localStorage.removeItem('currentName');
        localStorage.removeItem('currentUserId');
        this.currentUser = null;
    }

    /**
     * 获取当前用户显示名称
     * @returns {string} 显示名称
     */
    getCurrentUserName() {
        return localStorage.getItem('currentName') || 'User';
    }

    /**
     * 获取当前登录用户ID
     * @returns {number|null} 用户ID
     */
    getCurrentUserId() {
        const v = localStorage.getItem('currentUserId');
        return v ? parseInt(v, 10) : null;
    }

    /**
     * 生成带用户前缀的存储键
     * @param {string} suffix - 键后缀
     * @returns {string} 完整的存储键
     */
    getStorageKey(suffix) {
        if (!this.currentUser) {
            throw new Error('用户未登录');
        }
        return `${suffix}_${this.currentUser}`;
    }

    /**
     * 保存数据到本地存储
     * @param {string} key - 存储键
     * @param {any} data - 要保存的数据
     */
    saveToStorage(key, data) {
        try {
            const storageKey = this.getStorageKey(key);
            localStorage.setItem(storageKey, JSON.stringify(data));
        } catch (error) {
            console.error('保存数据失败:', error);
        }
    }

    /**
     * 从本地存储获取数据
     * @param {string} key - 存储键
     * @param {any} defaultValue - 默认值
     * @returns {any} 获取的数据
     */
    getFromStorage(key, defaultValue = null) {
        try {
            const storageKey = this.getStorageKey(key);
            const data = localStorage.getItem(storageKey);
            return data ? JSON.parse(data) : defaultValue;
        } catch (error) {
            console.error('获取数据失败:', error);
            return defaultValue;
        }
    }

    /**
     * 删除本地存储数据
     * @param {string} key - 存储键
     */
    removeFromStorage(key) {
        try {
            const storageKey = this.getStorageKey(key);
            localStorage.removeItem(storageKey);
        } catch (error) {
            console.error('删除数据失败:', error);
        }
    }

    /**
     * 获取聊天列表
     * @returns {Array} 聊天列表
     */
    getChatList() {
        return this.getFromStorage('chatList', []);
    }

    /**
     * 保存聊天列表
     * @param {Array} chatList - 聊天列表
     */
    saveChatList(chatList) {
        this.saveToStorage('chatList', chatList);
    }

    /**
     * 获取聊天历史记录
     * @param {string} chatId - 聊天ID
     * @returns {Array} 聊天历史
     */
    getChatHistory(chatId) {
        return this.getFromStorage(chatId, []);
    }

    /**
     * 保存聊天历史记录
     * @param {string} chatId - 聊天ID
     * @param {Array} history - 聊天历史
     */
    saveChatHistory(chatId, history) {
        this.saveToStorage(chatId, history);
    }

    /**
     * 删除聊天记录
     * @param {string} chatId - 聊天ID
     */
    deleteChatHistory(chatId) {
        this.removeFromStorage(chatId);
    }

    /**
     * 获取当前聊天ID
     * @returns {string|null} 当前聊天ID
     */
    getCurrentChatId() {
        return this.getFromStorage('currentChatId', null);
    }

    /**
     * 设置当前聊天ID
     * @param {string} chatId - 聊天ID
     */
    setCurrentChatId(chatId) {
        this.saveToStorage('currentChatId', chatId);
    }

    /**
     * 清除当前聊天ID
     */
    clearCurrentChatId() {
        this.removeFromStorage('currentChatId');
    }

    /**
     * 创建新的聊天记录
     * @param {string} title - 聊天标题
     * @returns {Object} 新的聊天对象
     */
    createNewChat(title = '新对话') {
        const now = Date.now();
        const newChat = {
            id: Utils.generateId('chat'),
            title: title,
            time: now
        };

        const chatList = this.getChatList();
        chatList.unshift(newChat);
        this.saveChatList(chatList);
        
        // 初始化空的聊天历史
        this.saveChatHistory(newChat.id, []);
        
        return newChat;
    }

    /**
     * 更新聊天标题
     * @param {string} chatId - 聊天ID
     * @param {string} newTitle - 新标题
     */
    updateChatTitle(chatId, newTitle) {
        const chatList = this.getChatList();
        const chat = chatList.find(c => c.id === chatId);
        if (chat) {
            chat.title = newTitle;
            chat.time = Date.now(); // 更新时间
            this.saveChatList(chatList);
        }
    }

    /**
     * 删除聊天
     * @param {string} chatId - 聊天ID
     */
    deleteChat(chatId) {
        // 删除聊天历史
        this.deleteChatHistory(chatId);
        
        // 从聊天列表中移除
        const chatList = this.getChatList();
        const updatedList = chatList.filter(c => c.id !== chatId);
        this.saveChatList(updatedList);
    }

    /**
     * 设置某个对话未读AI消息标记
     * @param {string} chatId
     */
    setChatUnread(chatId, unread = true) {
        const chatList = this.getChatList();
        const chat = chatList.find(c => c.id === chatId);
        if (chat) {
            chat.unread = unread;
            this.saveChatList(chatList);
        }
    }

    /**
     * 获取某个对话未读AI消息标记
     * @param {string} chatId
     */
    isChatUnread(chatId) {
        const chatList = this.getChatList();
        const chat = chatList.find(c => c.id === chatId);
        return chat && chat.unread;
    }

    /**
     * 清除所有用户数据
     */
    clearAllUserData() {
        if (!this.currentUser) return;
        
        // 获取所有相关的存储键
        const keys = [];
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            if (key && key.endsWith(`_${this.currentUser}`)) {
                keys.push(key);
            }
        }
        
        // 删除所有相关数据
        keys.forEach(key => localStorage.removeItem(key));
    }

    /**
     * 检查用户是否已登录
     * @returns {boolean} 是否已登录
     */
    isLoggedIn() {
        return !!this.currentUser;
    }

    /**
     * 获取存储使用统计
     * @returns {Object} 存储统计信息
     */
    getStorageStats() {
        const stats = {
            totalKeys: 0,
            userKeys: 0,
            totalSize: 0,
            userSize: 0
        };

        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            const value = localStorage.getItem(key);
            const size = (key.length + value.length) * 2; // 估算字节数

            stats.totalKeys++;
            stats.totalSize += size;

            if (this.currentUser && key.endsWith(`_${this.currentUser}`)) {
                stats.userKeys++;
                stats.userSize += size;
            }
        }

        return stats;
    }
}

// 创建全局存储管理实例
const storageManager = new StorageManager();

// 导出存储管理类
if (typeof module !== 'undefined' && module.exports) {
    module.exports = StorageManager;
}
