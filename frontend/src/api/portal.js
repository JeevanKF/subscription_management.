import api from './client'
export const mySubscriptions = () => api.get('/portal/subscriptions/')
export const myInvoices      = () => api.get('/portal/invoices/')

