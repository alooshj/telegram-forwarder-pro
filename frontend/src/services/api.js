/**
 * TeleTips Pro — API Client with Clerk JWT Injection
 * --------------------------------------------------
 * Intercepts all backend REST API requests and injects the active Clerk JWT token
 * into the `Authorization: Bearer <token>` header for seamless multi-tenant isolation.
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

export const createApiClient = (getToken) => {
  const request = async (endpoint, method = 'GET', body = null) => {
    const headers = {
      'Content-Type': 'application/json',
    };

    // 1. Inject Clerk session token if getToken is passed or available on window.Clerk
    let token = null;
    if (typeof getToken === 'function') {
      try {
        token = await getToken();
      } catch (err) {
        console.warn('Failed to retrieve Clerk JWT from hook:', err);
      }
    } else if (typeof window !== 'undefined' && window.Clerk?.session?.getToken) {
      try {
        token = await window.Clerk.session.getToken();
      } catch (err) {
        console.warn('Failed to retrieve Clerk JWT from window.Clerk:', err);
      }
    }

    // 2. Fallback to localStorage auth token
    if (!token && typeof localStorage !== 'undefined') {
      token = localStorage.getItem('teletips_auth_token');
    }

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const options = {
      method,
      headers,
      credentials: 'include', // Includes HTTP-only cookies
    };

    if (body) {
      options.body = JSON.stringify(body);
    }

    try {
      const response = await fetch(`${API_BASE_URL}${endpoint}`, options);
      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        return {
          success: false,
          status: response.status,
          error: data.error || `HTTP error! status: ${response.status}`,
          ...data,
        };
      }

      return data;
    } catch (err) {
      console.error(`API request error on ${endpoint}:`, err);
      return {
        success: false,
        error: err.message || 'Network error',
      };
    }
  };

  return {
    get: (endpoint) => request(endpoint, 'GET'),
    post: (endpoint, body) => request(endpoint, 'POST', body),
    put: (endpoint, body) => request(endpoint, 'PUT', body),
    delete: (endpoint) => request(endpoint, 'DELETE'),

    // Specific endpoints
    syncClerkUser: async (userData) => {
      let token = userData?.token || null;
      if (!token && typeof getToken === 'function') {
        try { token = await getToken(); } catch (e) {}
      } else if (!token && typeof window !== 'undefined' && window.Clerk?.session?.getToken) {
        try { token = await window.Clerk.session.getToken(); } catch (e) {}
      }
      return request('/api/auth/clerk-sync', 'POST', {
        ...userData,
        token: token || userData?.token || ''
      });
    },
    getStats: () => request('/api/stats', 'GET'),
    getRules: () => request('/api/rules', 'GET'),
    getLogs: (all = false) => request(`/api/logs${all ? '?all=true' : ''}`, 'GET'),
    clearLogs: (all = false) => request(`/api/logs/clear${all ? '?all=true' : ''}`, 'POST'),
    startForwarder: () => request('/api/forward/start', 'POST'),
    stopForwarder: () => request('/api/forward/stop', 'POST'),
  };
};
