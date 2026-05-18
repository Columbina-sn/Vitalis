// HTML/http.js - 修复版：支持 FormData 文件上传 + 自动重试（网络空闲断连）
(function() {
    const LOGIN_PAGE_URL = '/HTML/Index/index.html';

    function getToken() {
        return localStorage.getItem('access_token');
    }

    function redirectToLogin() {
        localStorage.removeItem('access_token');
        localStorage.removeItem('user_base_info');
        if (!window.location.pathname.includes('/Index/')) {
            window.location.href = LOGIN_PAGE_URL;
        }
    }

    /**
     * 带重试的 fetch 封装
     * @param {string} url     请求地址
     * @param {object} options fetch 选项
     * @param {number} retries 剩余重试次数
     * @returns {Promise<Response>}
     */
    async function fetchWithRetry(url, options, retries = 3) {
        try {
            const response = await fetch(url, options);
            return response;
        } catch (err) {
            // 网络错误（包括连接断开、空闲断连、DNS失败等）
            if (retries > 0 && (err.name === 'TypeError' || err.name === 'AbortError' || err.message?.includes('Network'))) {
                console.warn(`请求失败，剩余重试次数: ${retries}`, err);
                await new Promise(resolve => setTimeout(resolve, 1000)); // 等待1秒
                return fetchWithRetry(url, options, retries - 1);
            }
            throw err;
        }
    }

    window.http = async function(config) {
        const { method, url, params, data, needAuth = true } = config;
        let finalUrl = url;

        if (params) {
            const queryString = new URLSearchParams(params).toString();
            finalUrl += `?${queryString}`;
        }

        const options = {
            method: method,
            headers: {},
        };

        const isFormData = data instanceof FormData;

        if (!isFormData) {
            options.headers['Content-Type'] = 'application/json';
            if (data) {
                options.body = JSON.stringify(data);
            }
        } else {
            options.body = data;
        }

        if (needAuth) {
            const token = getToken();
            if (!token) {
                redirectToLogin();
                throw new Error('未登录，请先登录');
            }
            options.headers['Authorization'] = `Bearer ${token}`;
        }

        let response;
        try {
            // 使用带重试的 fetch
            response = await fetchWithRetry(finalUrl, options, 2);
        } catch (err) {
            // 重试后仍失败，抛出更友好的错误
            throw new Error('网络连接失败，请检查网络后重试');
        }

        let responseData;
        try {
            responseData = await response.json();
        } catch (e) {
            throw new Error('服务器返回数据异常');
        }

        // 401 未授权处理（保持不变）
        if (response.status === 401 && needAuth === true) {
            const errMsg = responseData?.detail || '登录已过期，请重新登录';
            if (typeof window.showToast === 'function') {
                window.showToast(`⚠️ ${errMsg}`, 5000);
            }
            setTimeout(() => {
                redirectToLogin();
            }, 5000);
            const error = new Error(errMsg);
            error.status = 401;
            error.original = responseData;
            error.alreadyHandled = true;
            throw error;
        }

        if (response.status === 401 && needAuth === false) {
            const errMsg = responseData?.detail || responseData?.message || '认证失败';
            const error = new Error(errMsg);
            error.status = 401;
            error.original = responseData;
            throw error;
        }

        if (response.status === 403 && needAuth === true) {
            const detail = responseData?.detail || '';
            if (detail.includes('账号已被禁止登录')) {
                window.showToast && window.showToast('🚫 账号已被禁止登录，即将返回登录页', 5000);
                setTimeout(() => {
                    redirectToLogin();
                }, 5000);
                const error = new Error(detail);
                error.status = 403;
                error.original = responseData;
                error.alreadyHandled = true;
                throw error;
            }
            const otherMsg = responseData?.detail || `权限不足 (${response.status})`;
            const err = new Error(otherMsg);
            err.status = 403;
            err.original = responseData;
            throw err;
        }

        if (!response.ok) {
            const errorMsg = responseData?.detail || responseData?.message || `请求失败 (${response.status})`;
            const customError = new Error(errorMsg);
            customError.status = response.status;
            customError.original = responseData;
            throw customError;
        }

        return responseData.data !== undefined ? responseData.data : responseData;
    };
})();