import api from './client'
export const list = () => api.get('/products/')
export const get  = (id) => api.get(`/products/${id}/`)

