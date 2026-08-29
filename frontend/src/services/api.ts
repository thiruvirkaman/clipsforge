import axios from 'axios';

// Relative path: in Docker, nginx proxies /api -> the backend service
// (same origin, no CORS needed); in local dev, vite.config.ts proxies /api
// to the local backend. This avoids ever needing to bake an absolute API
// URL into the built bundle at Docker build time.
const API_BASE = '/api/v1';

const api = axios.create({
  baseURL: API_BASE,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    if (error.response?.status === 401 && !error.config._retry) {
      error.config._retry = true;
      const refresh = localStorage.getItem('refresh_token');
      const { data } = await axios.post(`${API_BASE}/auth/refresh`, {
        refresh_token: refresh,
      });
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);
      return api(error.config);
    }
    return Promise.reject(error);
  }
);

export default api;
