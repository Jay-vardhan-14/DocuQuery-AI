/**
 * API client for DocuQuery AI backend.
 *
 * All requests are routed through the Vite dev proxy (/api → localhost:8000).
 * Handles JWT token management, automatic 401 logout, and JSON parsing.
 */

const API_BASE = '/api/v1';

/**
 * Get stored auth tokens.
 */
export function getTokens() {
  const raw = localStorage.getItem('docuquery_auth');
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

/**
 * Store auth tokens.
 */
export function setTokens(tokens) {
  localStorage.setItem('docuquery_auth', JSON.stringify(tokens));
}

/**
 * Clear stored auth tokens.
 */
export function clearTokens() {
  localStorage.removeItem('docuquery_auth');
}

/**
 * Make an authenticated API request.
 */
async function request(path, options = {}) {
  const tokens = getTokens();
  const headers = {
    ...options.headers,
  };

  // Don't set Content-Type for FormData (browser sets boundary automatically)
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }

  if (tokens?.access_token) {
    headers['Authorization'] = `Bearer ${tokens.access_token}`;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  // Handle 401: clear tokens and reload
  if (response.status === 401) {
    clearTokens();
    window.location.href = '/login';
    throw new Error('Session expired');
  }

  return response;
}

/**
 * Parse JSON response, throwing on error status.
 */
async function parseResponse(response) {
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || `Request failed (${response.status})`);
  }
  return data;
}

// ---------------------------------------------------------------------------
// Auth API
// ---------------------------------------------------------------------------

export const authApi = {
  async login(email, password) {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    return parseResponse(res);
  },

  async register(email, password, fullName) {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, full_name: fullName }),
    });
    return parseResponse(res);
  },

  async getProfile() {
    const res = await request('/auth/me');
    return parseResponse(res);
  },

  async refreshToken(refreshToken) {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    return parseResponse(res);
  },
};

// ---------------------------------------------------------------------------
// Query API
// ---------------------------------------------------------------------------

export const queryApi = {
  async ask(question) {
    const res = await request('/query', {
      method: 'POST',
      body: JSON.stringify({ question }),
    });
    return parseResponse(res);
  },

  async getHistory() {
    const res = await request('/query/history');
    return parseResponse(res);
  },
};

// ---------------------------------------------------------------------------
// Documents API
// ---------------------------------------------------------------------------

export const documentsApi = {
  async list() {
    const res = await request('/documents');
    return parseResponse(res);
  },

  async upload(file, title, accessLevel) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', title);
    formData.append('access_level', accessLevel);

    const res = await request('/documents/upload', {
      method: 'POST',
      body: formData,
    });
    return parseResponse(res);
  },

  async getStatus(docId) {
    const res = await request(`/documents/${docId}/status`);
    return parseResponse(res);
  },

  async update(docId, data) {
    const res = await request(`/documents/${docId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
    return parseResponse(res);
  },

  async remove(docId) {
    const res = await request(`/documents/${docId}`, {
      method: 'DELETE',
    });
    if (!res.ok && res.status !== 204) {
      const data = await res.json();
      throw new Error(data.detail || 'Delete failed');
    }
  },
};

// ---------------------------------------------------------------------------
// Admin API
// ---------------------------------------------------------------------------

export const adminApi = {
  async listUsers() {
    const res = await request('/admin/users');
    return parseResponse(res);
  },

  async updateUser(userId, data) {
    const res = await request(`/admin/users/${userId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
    return parseResponse(res);
  },

  async getAuditLogs(params = {}) {
    const query = new URLSearchParams();
    if (params.page) query.set('page', params.page);
    if (params.pageSize) query.set('page_size', params.pageSize);
    if (params.userId) query.set('user_id', params.userId);
    const qs = query.toString();
    const res = await request(`/admin/audit-logs${qs ? '?' + qs : ''}`);
    return parseResponse(res);
  },

  async getMetrics() {
    const res = await request('/admin/metrics');
    return parseResponse(res);
  },
};
