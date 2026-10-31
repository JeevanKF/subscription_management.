import api from './client'
export const getSummary = () => api.get('/dashboard/')

