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

    // Inject Clerk session token if getToken is available
    if (typeof getToken === 'function') {
      try {
        const token = await getToken();
        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }
      } catch (err) {
        console.warn('Failed to retrieve Clerk JWT:', err);
      }
    }

    const options = {
      method,
      headers,
      credentials: 'include', // Includes HTTP-only cookies
    };

    if (body) {
      options.body = JSON.stringify(body);
    }

    const response = await fetch(`${API_BASE_URL}${endpoint}`, options);
    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(data.error || `HTTP error! status: ${response.status}`);
    }

    return data;
  };

  return {
    get: (endpoint) => request(endpoint, 'GET'),
    post: (endpoint, body) => request(endpoint, 'POST', body),
    put: (endpoint, body) => request(endpoint, 'PUT', body),
    delete: (endpoint) => request(endpoint, 'DELETE'),

    // Specific endpoints
    syncClerkUser: (userData) => request('/api/auth/clerk-sync', 'POST', userData),
    getStats: () => request('/api/stats', 'GET'),
    getRules: () => request('/api/rules', 'GET'),
    getLogs: (all = false) => request(`/api/logs${all ? '?all=true' : ''}`, 'GET'),
    clearLogs: (all = false) => request(`/api/logs/clear${all ? '?all=true' : ''}`, 'POST'),
    startForwarder: () => request('/api/forward/start', 'POST'),
    stopForwarder: () => request('/api/forward/stop', 'POST'),
  };
};
