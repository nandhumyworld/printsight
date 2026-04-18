import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import type { LoginRequest, LoginResponse, RegisterRequest, User, UpdateProfileRequest } from '@/types';

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8001';

export const api = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: { 'Content-Type': 'application/json' },
});

// Inject token
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem('access_token');
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Auto-refresh on 401
let isRefreshing = false;
let waitQueue: Array<(token: string) => void> = [];

api.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & { _retry?: boolean };
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;
      const refreshToken = localStorage.getItem('refresh_token');
      if (!refreshToken) {
        if (window.location.pathname !== '/login') window.location.href = '/login';
        return Promise.reject(error);
      }
      if (isRefreshing) {
        return new Promise((resolve) => {
          waitQueue.push((token) => {
            original.headers.Authorization = `Bearer ${token}`;
            resolve(api(original));
          });
        });
      }
      isRefreshing = true;
      try {
        const { data } = await axios.post<LoginResponse>(
          `${API_URL}/api/v1/auth/refresh`,
          { refresh_token: refreshToken }
        );
        localStorage.setItem('access_token', data.access_token);
        waitQueue.forEach((cb) => cb(data.access_token));
        waitQueue = [];
        original.headers.Authorization = `Bearer ${data.access_token}`;
        return api(original);
      } catch {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        if (window.location.pathname !== '/login') window.location.href = '/login';
        return Promise.reject(error);
      } finally {
        isRefreshing = false;
      }
    }
    return Promise.reject(error);
  }
);

// Auth service functions
export const authApi = {
  login: (data: LoginRequest) => api.post<LoginResponse>('/auth/login', data),
  register: (data: RegisterRequest) => api.post<User>('/auth/register', data),
  logout: (refreshToken: string) => api.post('/auth/logout', { refresh_token: refreshToken }),
  refresh: (refreshToken: string) => api.post<LoginResponse>('/auth/refresh', { refresh_token: refreshToken }),
  me: () => api.get<User>('/auth/me'),
  updateProfile: (data: UpdateProfileRequest) => api.put<User>('/auth/me', data),
};
