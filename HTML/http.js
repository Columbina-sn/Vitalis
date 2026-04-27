// HTML\http.js - 修复版：支持 FormData 文件上传
(function() {
    // 登录页面的URL路径，用于未登录时跳转
    const LOGIN_PAGE_URL = '/HTML/Index/index.html';

    // 从 localStorage 获取存储的 access_token
    function getToken() {
        return localStorage.getItem('access_token');
    }

    // 清除 token 并跳转到登录页（如果当前不在登录页）
    function redirectToLogin() {
        localStorage.removeItem('access_token');               // 删除失效的 token
        if (!window.location.pathname.includes('/Index/')) {  // 避免重复跳转登录页
            window.location.href = LOGIN_PAGE_URL;            // 跳转到登录页
        }
    }

    // 暴露全局 http 函数，用于发起带认证的请求
    window.http = async function(config) {
        // 解构配置项：请求方法、URL、查询参数、请求体数据、是否需要认证（默认需要）
        const { method, url, params, data, needAuth = true } = config;
        let finalUrl = url;

        // 如果存在查询参数，将其拼接到 URL 后面
        if (params) {
            const queryString = new URLSearchParams(params).toString();
            finalUrl += `?${queryString}`;
        }

        // 初始化 fetch 选项对象
        const options = {
            method: method,
            headers: {},
        };

        // 关键判断：data 是否为 FormData 类型（用于文件上传）
        const isFormData = data instanceof FormData;

        if (!isFormData) {
            // 非 FormData：按 JSON 格式发送数据
            options.headers['Content-Type'] = 'application/json';
            if (data) {
                options.body = JSON.stringify(data);   // 将 JS 对象转为 JSON 字符串
            }
        } else {
            // FormData：不设置 Content-Type，让浏览器自动生成 multipart/form-data 和边界
            options.body = data;                       // 直接将 FormData 对象赋给 body
        }

        // 如果需要认证，则添加 Authorization 头
        if (needAuth) {
            const token = getToken();                  // 获取当前 token
            if (!token) {                              // 没有 token 则未登录
                redirectToLogin();                     // 跳转登录页
                throw new Error('未登录，请先登录');
            }
            options.headers['Authorization'] = `Bearer ${token}`;  // 添加 Bearer 令牌
        }

        let response;
        try {
            // 发起 fetch 请求
            response = await fetch(finalUrl, options);
        } catch (err) {
            // 网络请求失败（如断网）
            throw new Error('网络连接失败，请检查网络');
        }

        let responseData;
        try {
            // 尝试解析响应为 JSON
            responseData = await response.json();
        } catch (e) {
            // 响应不是合法 JSON 格式
            throw new Error('服务器返回数据异常');
        }

        // 处理 401 未授权（需要认证的接口）
        if (response.status === 401 && needAuth === true) {
            redirectToLogin();                         // 清除 token 并跳转登录页
            const errMsg = responseData?.detail || '登录已过期，请重新登录';
            const error = new Error(errMsg);
            error.status = 401;
            error.original = responseData;
            throw error;
        }

        // 处理 401 但 needAuth 为 false（可选认证接口认证失败）
        if (response.status === 401 && needAuth === false) {
            const errMsg = responseData?.detail || responseData?.message || '认证失败';
            const error = new Error(errMsg);
            error.status = 401;
            error.original = responseData;
            throw error;
        }

        // 处理 403 禁止登录（账号被封禁）
        if (response.status === 403 && needAuth === true) {
            const detail = responseData?.detail || '';
            if (detail.includes('账号已被禁止登录')) {
                // 显示提示，然后延迟跳转回登录页
                window.showToast && window.showToast('🚫 账号已被禁止登录，即将返回登录页', 2500);
                localStorage.removeItem('access_token');
                // 用 setTimeout 确保提示可见，且不会被后续错误处理取消跳转
                setTimeout(() => {
                    window.location.replace(LOGIN_PAGE_URL);
                }, 2000);
                const error = new Error(detail);
                error.status = 403;
                error.original = responseData;
                throw error;
            }
            // 其他 403（如管理员熔断）按原样抛出
            const otherMsg = responseData?.detail || `权限不足 (${response.status})`;
            const err = new Error(otherMsg);
            err.status = 403;
            err.original = responseData;
            throw err;
        }

        // 处理其他非 2xx 状态码
        if (!response.ok) {
            const errorMsg = responseData?.detail || responseData?.message || `请求失败 (${response.status})`;
            const customError = new Error(errorMsg);
            customError.status = response.status;
            customError.original = responseData;
            throw customError;
        }

        // 成功响应：如果响应数据中有 data 字段则返回它，否则返回整个响应对象
        return responseData.data !== undefined ? responseData.data : responseData;
    };
})();