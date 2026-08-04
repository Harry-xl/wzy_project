/**
 * 工具函数模块
 * 提供常用的工具函数
 */

class Utils {
    /**
     * 验证邮箱格式
     * @param {string} email - 邮箱地址
     * @returns {boolean} 是否为有效邮箱
     */
    static validateEmail(email) {
        const emailReg = /^[\w.-]+@[\w.-]+\.[a-zA-Z]{2,}$/;
        return emailReg.test(email);
    }

    /**
     * 显示或隐藏邮箱错误提示
     * @param {string} errorElementId - 错误元素ID
     * @param {boolean} show - 是否显示
     * @param {string} message - 错误消息
     */
    static showEmailError(errorElementId, show = true, message = '邮箱格式不正确') {
        const errorEl = document.getElementById(errorElementId);
        if (errorEl) {
            if (show) {
                errorEl.textContent = message;
                errorEl.style.display = 'block';
            } else {
                errorEl.style.display = 'none';
            }
        }
    }

    /**
     * 显示通用错误提示
     * @param {string} message - 错误消息
     * @param {number} duration - 显示时长（毫秒）
     */
    static showToast(message, duration = 3000) {
        // 创建toast元素
        const toast = document.createElement('div');
        toast.className = 'toast';
        toast.textContent = message;
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: #ff4757;
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            z-index: 10000;
            font-size: 14px;
            animation: slideIn 0.3s ease-out;
        `;

        // 添加CSS动画
        if (!document.getElementById('toast-styles')) {
            const style = document.createElement('style');
            style.id = 'toast-styles';
            style.textContent = `
                @keyframes slideIn {
                    from { transform: translateX(100%); opacity: 0; }
                    to { transform: translateX(0); opacity: 1; }
                }
                @keyframes slideOut {
                    from { transform: translateX(0); opacity: 1; }
                    to { transform: translateX(100%); opacity: 0; }
                }
            `;
            document.head.appendChild(style);
        }

        document.body.appendChild(toast);

        // 自动移除
        setTimeout(() => {
            toast.style.animation = 'slideOut 0.3s ease-in';
            setTimeout(() => {
                document.body.removeChild(toast);
            }, 300);
        }, duration);
    }

    /**
     * 防抖函数
     * @param {Function} func - 要防抖的函数
     * @param {number} wait - 等待时间
     * @param {boolean} immediate - 是否立即执行
     * @returns {Function} 防抖后的函数
     */
    static debounce(func, wait, immediate = false) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                timeout = null;
                if (!immediate) func(...args);
            };
            const callNow = immediate && !timeout;
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
            if (callNow) func(...args);
        };
    }

    /**
     * 节流函数
     * @param {Function} func - 要节流的函数
     * @param {number} limit - 时间限制
     * @returns {Function} 节流后的函数
     */
    static throttle(func, limit) {
        let inThrottle;
        return function(...args) {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }

    /**
     * 格式化日期
     * @param {Date|number} timestamp - 时间戳或日期对象
     * @param {string} format - 格式类型 ('date', 'datetime', 'time')
     * @returns {string} 格式化后的日期字符串
     */
    static formatDate(timestamp, format = 'date') {
        const date = timestamp ? new Date(timestamp) : new Date();
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        const seconds = String(date.getSeconds()).padStart(2, '0');

        switch (format) {
            case 'datetime':
                return `${year}-${month}-${day} ${hours}:${minutes}`;
            case 'time':
                return `${hours}:${minutes}:${seconds}`;
            case 'date':
            default:
                return `${year}-${month}-${day}`;
        }
    }

    /**
     * 生成唯一ID
     * @param {string} prefix - 前缀
     * @returns {string} 唯一ID
     */
    static generateId(prefix = 'id') {
        return `${prefix}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    /**
     * 安全的JSON解析
     * @param {string} str - JSON字符串
     * @param {any} defaultValue - 默认值
     * @returns {any} 解析结果
     */
    static safeJsonParse(str, defaultValue = null) {
        try {
            return JSON.parse(str);
        } catch (e) {
            console.warn('JSON解析失败:', e);
            return defaultValue;
        }
    }

    /**
     * 深度克隆对象
     * @param {any} obj - 要克隆的对象
     * @returns {any} 克隆后的对象
     */
    static deepClone(obj) {
        if (obj === null || typeof obj !== 'object') return obj;
        if (obj instanceof Date) return new Date(obj.getTime());
        if (obj instanceof Array) return obj.map(item => Utils.deepClone(item));
        if (typeof obj === 'object') {
            const clonedObj = {};
            for (const key in obj) {
                if (obj.hasOwnProperty(key)) {
                    clonedObj[key] = Utils.deepClone(obj[key]);
                }
            }
            return clonedObj;
        }
    }

    /**
     * 滚动到元素位置
     * @param {HTMLElement} element - 目标元素
     * @param {Object} options - 滚动选项
     */
    static scrollToElement(element, options = { behavior: 'smooth', block: 'center' }) {
        if (element && element.scrollIntoView) {
            element.scrollIntoView(options);
        }
    }

    /**
     * 检查元素是否在视口中
     * @param {HTMLElement} element - 要检查的元素
     * @returns {boolean} 是否在视口中
     */
    static isElementInViewport(element) {
        const rect = element.getBoundingClientRect();
        return (
            rect.top >= 0 &&
            rect.left >= 0 &&
            rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
            rect.right <= (window.innerWidth || document.documentElement.clientWidth)
        );
    }
}

// 导出工具类
/**
 * 将实力值映射为等级标签与颜色
 * 阈值区间：
 * - [0.00, 0.40)：初级（红色）
 * - [0.40, 0.70)：中级（橙色）
 * - [0.70, 0.90)：高级（绿色）
 * - [0.90, 1.00]：专家（深绿色）
 * @param {number} value - 实力值，范围建议为 [0, 1]
 * @returns {{label:string, color:string}} 等级与颜色
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
 * 在容器内绘制简单的 SVG 折线图，展示用户实力的趋势
 * @param {HTMLElement} container - 渲染的容器元素
 * @param {{t:string, value:number}[]} trendData - 实力趋势数据点数组
 * @returns {void}
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
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Utils;
}
