// utils.js - 全局工具函数（Toast、日期格式化、HTML转义）
(function() { // 立即执行函数，避免污染全局作用域

    // ---------- Toast 悬浮提示 ----------
    const toastContainer = document.getElementById('toastContainer'); // 获取Toast容器DOM元素，用于放置提示卡片
    let activeToasts = []; // 存储当前活跃（未消失）的Toast元素数组，用于限制同时显示数量

    window.showToast = function(message, duration = 5000) { // 全局函数：显示悬浮提示，参数为消息文本和显示时长（默认5秒）
        if (!toastContainer) { // 如果Toast容器不存在（DOM中未找到）
            console.warn('toastContainer not found'); // 在控制台输出警告信息
            return; // 提前退出函数，不执行后续提示逻辑
        }
        if (activeToasts.length >= 3) { // 如果当前活跃的Toast数量已达到上限（3个）
            const oldest = activeToasts.shift(); // 从数组中移除最早的一个Toast元素，并保存到变量oldest
            if (oldest && oldest.parentNode) { // 如果该Toast元素存在且仍有父节点（即还在DOM树中）
                oldest.classList.add('fade-out'); // 为它添加淡出动画类，使其逐渐消失
                setTimeout(() => oldest.remove(), 300); // 设置300毫秒后从DOM中移除该元素（动画时长匹配）
            }
        }
        const toast = document.createElement('div'); // 创建一个新的div元素作为Toast卡片
        toast.className = 'toast-card'; // 设置类名为toast-card，用于样式和动画
        toast.textContent = message; // 将传入的消息文本赋值给Toast的文本内容
        toastContainer.appendChild(toast); // 将Toast卡片添加到容器中，使其出现在页面上
        activeToasts.push(toast); // 将新创建的Toast元素加入活跃数组，便于后续管理

        setTimeout(() => { // 设置定时器，在指定时长后自动移除Toast
            if (toast && toast.parentNode) { // 如果Toast元素存在且仍挂在DOM树上
                toast.classList.add('fade-out'); // 添加淡出动画类，开始消失动画
                setTimeout(() => { // 等待动画结束后彻底移除
                    if (toast.parentNode) toast.remove(); // 如果Toast还有父节点，则从DOM中移除
                    const idx = activeToasts.indexOf(toast); // 查找当前Toast在活跃数组中的索引位置
                    if (idx !== -1) activeToasts.splice(idx, 1); // 如果找到了，则从数组中删除该元素
                }, 300); // 延迟300毫秒，与CSS动画时长一致
            }
        }, duration); // 定时器的等待时间为用户指定的duration（默认5000毫秒）
    };

    // ---------- 日期格式化 ----------
    window.formatDate = function(isoString) { // 全局函数：将ISO日期字符串格式化为更友好的展示形式
        if (!isoString) return '近期'; // 如果传入的日期字符串为空或假值，返回默认文案'近期'
        try { // 尝试执行日期解析和格式化，防止非法字符串导致崩溃
            const date = new Date(isoString); // 使用ISO字符串创建Date对象
            const now = new Date(); // 获取当前时间的Date对象，用于比较年份
            const thisYear = now.getFullYear(); // 获取当前年份（如2026）
            const year = date.getFullYear(); // 获取传入日期的年份
            const month = date.getMonth() + 1; // 获取月份（0-11，需+1转为1-12）
            const day = date.getDate(); // 获取日期（几号）
            if (year === thisYear) { // 如果年份与当前年份相同
                return `${month}月${day}日`; // 返回“X月X日”格式，省略年份
            } else { // 年份不同（如往年或未来）
                return `${year}年${month}月${day}日`; // 返回完整“XXXX年X月X日”格式
            }
        } catch(e) { // 如果解析过程中抛出异常（如无效日期字符串）
            return '未知日期'; // 返回兜底文案
        }
    };

    // ---------- HTML 转义（防XSS）----------
    window.escapeHtml = function(str) { // 全局函数：将字符串中的特殊字符转义为HTML实体，防止XSS攻击
        if (!str) return ''; // 如果输入为空或假值，直接返回空字符串
        return str.replace(/[&<>]/g, function(m) { // 使用正则匹配&、<、>三个危险字符，并用替换函数处理
            if (m === '&') return '&amp;'; // 将&替换为&amp;实体
            if (m === '<') return '&lt;';  // 将<替换为&lt;实体
            if (m === '>') return '&gt;';  // 将>替换为&gt;实体
            if (m === '"') return '&quot;';
            if (m === "'") return '&#39;';
            return m; // 其他匹配到的字符（理论上只有这三个）原样返回（实际不会执行到）
        });
    };
})(); // 立即执行函数结束

// ---------- 主题管理 ----------
(function() {
    // 获取当前系统主题偏好 (dark/light)
    function getSystemTheme() {
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }

    // 根据主题模式设置 data-theme 属性
    // mode: 0=浅色, 1=深色, 2=跟随系统
    window.applyTheme = function(mode) {
        const body = document.body;
        if (!body) return;
        if (mode === 0) {
            body.setAttribute('data-theme', 'light');
        } else if (mode === 1) {
            body.setAttribute('data-theme', 'dark');
        } else {
            const sys = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
            body.setAttribute('data-theme', sys);
        }
        localStorage.setItem('theme_mode', mode);

        // 更新主题按钮 active 状态（仅当按钮存在时）
        const lightBtn = document.getElementById('themeLightBtn');
        const darkBtn = document.getElementById('themeDarkBtn');
        const autoBtn = document.getElementById('themeAutoBtn');
        if (lightBtn) lightBtn.classList.toggle('active', mode === 0);
        if (darkBtn) darkBtn.classList.toggle('active', mode === 1);
        if (autoBtn) autoBtn.classList.toggle('active', mode === 2);
    };

    // 监听系统主题变化，仅在跟随系统模式下自动切换
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
        const stored = localStorage.getItem('theme_mode');
        if (stored == null || stored === '2') {
            window.applyTheme(2);
        }
    });

    // 初始化主题：优先从 localStorage 读取，无则默认跟随系统
    window.initTheme = function() {
        const stored = localStorage.getItem('theme_mode');
        const mode = stored !== null ? parseInt(stored) : 2;
        window.applyTheme(mode);
    };

    // 页面加载时立即调用一次
    window.initTheme();
})();