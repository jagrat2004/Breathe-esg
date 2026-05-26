import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({ baseURL: API_BASE });

api.interceptors.request.use(config => {
  const token = localStorage.getItem('auth_token');
  if (token) config.headers.Authorization = `Token ${token}`;
  return config;
});

export const login = async (username, password) => {
  const res = await api.post('/api/auth/token/', { username, password });
  localStorage.setItem('auth_token', res.data.token);
  return res.data;
};

export const logout = () => localStorage.removeItem('auth_token');

export const getDashboard = () => api.get('/api/dashboard/');
export const getRecords = (params) => api.get('/api/records/', { params });
export const approveRecord = (id, note) => api.post(`/api/records/${id}/approve/`, { note: note || '' });
export const rejectRecord = (id, note) => api.post(`/api/records/${id}/reject/`, { note: note || '' });
export const bulkApprove = (ids) => api.post('/api/records/bulk_approve/', { ids });
export const lockApproved = () => api.post('/api/records/lock_approved/');
export const getBatches = () => api.get('/api/batches/');
export const ingestFile = (file, source_type, country) => {
  const form = new FormData();
  form.append('file', file);
  form.append('source_type', source_type);
  if (country) form.append('country', country);
  return api.post('/api/ingest/', form);
};

export default api;
