import axios from 'axios';

// Defaults to a relative path: in Docker, nginx proxies /api -> the backend
// service (same origin, no CORS needed); in local dev, vite.config.ts
// proxies /api to the local backend -- so most deployments never need to
// set VITE_API_URL at all. Set it (as a Docker build ARG) only when the
// frontend and backend are deliberately served from different origins
// (e.g. shorts.example.com / api.example.com) and the browser must call
// the API domain directly. Checked for truthiness, not just interpolated,
// so an *unset* VITE_API_URL never bakes in the literal string "undefined".
const API_BASE = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api/v1`
  : '/api/v1';

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
