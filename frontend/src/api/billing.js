/**
 * src/api/billing.js
 * API client methods for Module M3.
 */
import api from './client'

// Invoices
export const listInvoices = (params) => api.get('/billing/invoices/', { params })
export const getInvoice = (uuid) => api.get(`/billing/invoices/${uuid}/`)
export const confirmInvoice = (uuid) => api.post(`/billing/invoices/${uuid}/confirm/`)
export const sendInvoice = (uuid) => api.post(`/billing/invoices/${uuid}/send/`)
export const cancelInvoice = (uuid, reason) => api.post(`/billing/invoices/${uuid}/cancel/`, { reason })
export const recordPayment = (uuid, data) => api.post(`/billing/invoices/${uuid}/pay/`, data)
export const sendReminder = (uuid) => api.post(`/billing/invoices/${uuid}/remind/`)

// Billing Run
export const previewBilling = (target_date) =>
  api.get('/billing/run/preview/', { params: { target_date } })
export const executeBillingRun = (data) => api.post('/billing/run/', data)

// Discounts
export const listDiscounts = () => api.get('/billing/discounts/')
export const createDiscount = (data) => api.post('/billing/discounts/', data)
export const deleteDiscount = (id) => api.delete(`/billing/discounts/${id}/`)

// CSV Exports (triggers download)
export const exportInvoicesUrl = () => '/api/billing/invoices/export/'
export const exportPaymentsUrl = () => '/api/billing/payments/export/'
