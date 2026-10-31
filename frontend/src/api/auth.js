/**
 * src/api/auth.js
 */
import api from './client'

export const login  = (username, password) =>
  api.post('/auth/login/', { username, password })

export const logout = () => api.post('/auth/logout/')

export const getMe  = () => api.get('/auth/me/')

export const healthCheck = () => api.get('/auth/health/')

