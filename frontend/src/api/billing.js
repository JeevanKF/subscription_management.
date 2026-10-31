import api from './client'
export const listInvoices   = ()     => api.get('/billing/invoices/')
export const getInvoice     = (id)   => api.get(`/billing/invoices/${id}/`)
export const listDiscounts  = ()     => api.get('/billing/discounts/')

