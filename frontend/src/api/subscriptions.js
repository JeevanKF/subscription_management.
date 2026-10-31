import api from './client'
export const list   = ()     => api.get('/subscriptions/')
export const get    = (id)   => api.get(`/subscriptions/${id}/`)
export const create = (data) => api.post('/subscriptions/', data)
export const update = (id, data) => api.patch(`/subscriptions/${id}/`, data)

