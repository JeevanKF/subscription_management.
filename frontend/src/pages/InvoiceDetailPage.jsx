/**
 * src/pages/InvoiceDetailPage.jsx
 * Printable Invoice Detail View & Action Center:
 * - IDOR-proof UUID routing
 * - Actions: Confirm, Send, Record Payment, Send Reminder, Cancel, Print
 * - Embedded Record Payment Modal
 * - Status History Audit Trail
 */

import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { billingApi } from '../api'

export default function InvoiceDetailPage() {
  const { uuid } = useParams()
  const navigate = useNavigate()
  const [invoice, setInvoice] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // Payment modal state
  const [showPayModal, setShowPayModal] = useState(false)
  const [payAmount, setPayAmount] = useState('')
  const [payDate, setPayDate] = useState(() => new Date().toISOString().split('T')[0])
  const [payMethod, setPayMethod] = useState('bank_transfer')
  const [payRef, setPayRef] = useState('')
  const [payNote, setPayNote] = useState('')
  const [submittingPayment, setSubmittingPayment] = useState(false)

  useEffect(() => {
    loadInvoice()
  }, [uuid])

  async function loadInvoice() {
    setLoading(true)
    try {
      const res = await billingApi.getInvoice(uuid)
      setInvoice(res.data)
      setPayAmount(res.data.balance_due)
    } catch (err) {
      setError(err.response?.status === 404 ? 'Invoice not found or unauthorized.' : 'Failed to load invoice.')
    }
    setLoading(false)
  }

  async function handleConfirm() {
    try {
      const res = await billingApi.confirmInvoice(uuid)
      setInvoice(res.data)
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to confirm')
    }
  }

  async function handleSend() {
    try {
      const res = await billingApi.sendInvoice(uuid)
      setInvoice(res.data)
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to send')
    }
  }

  async function handleCancel() {
    const reason = prompt('Enter cancellation reason:')
    if (reason === null) return
    try {
      const res = await billingApi.cancelInvoice(uuid, reason)
      setInvoice(res.data)
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to cancel')
    }
  }

  async function handleRemind() {
    try {
      const res = await billingApi.sendReminder(uuid)
      alert(`Reminder recorded! Last reminded: ${res.data.last_reminded_date} (Count: ${res.data.reminder_count})`)
      loadInvoice()
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to send reminder')
    }
  }

  async function handleRecordPayment(e) {
    e.preventDefault()
    setSubmittingPayment(true)
    try {
      const res = await billingApi.recordPayment(uuid, {
        amount: Number(payAmount),
        payment_date: payDate,
        method: payMethod,
        reference: payRef,
        note: payNote,
      })
      setInvoice(res.data.invoice)
      setShowPayModal(false)
      setPayRef('')
      setPayNote('')
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to record payment')
    }
    setSubmittingPayment(false)
  }

  if (loading) return <div className="text-center py-5">Loading invoice...</div>
  if (error) return <div className="alert alert-danger my-4">{error}</div>
  if (!invoice) return null

  return (
    <div className="container py-3">
      {/* Top Action Bar (hidden on print) */}
      <div className="d-flex justify-content-between align-items-center mb-4 d-print-none">
        <Link to="/billing" className="btn btn-outline-secondary">
          ← Back to Invoices
        </Link>
        <div className="d-flex gap-2">
          {invoice.status === 'draft' && (
            <button className="btn btn-primary" onClick={handleConfirm}>
              ✓ Confirm Invoice
            </button>
          )}
          {(invoice.status === 'confirmed' || invoice.status === 'draft') && (
            <button className="btn btn-info text-white" onClick={handleSend}>
              ✉ Send Invoice
            </button>
          )}
          {Number(invoice.balance_due) > 0 && invoice.status !== 'cancelled' && (
            <button className="btn btn-success" onClick={() => setShowPayModal(true)}>
              ₹ Record Payment
            </button>
          )}
          {(invoice.status === 'sent' || invoice.status === 'overdue') && (
            <button className="btn btn-warning" onClick={handleRemind}>
              🔔 Send Reminder ({invoice.reminder_count})
            </button>
          )}
          {invoice.status !== 'paid' && invoice.status !== 'cancelled' && (
            <button className="btn btn-outline-danger" onClick={handleCancel}>
              ✕ Cancel
            </button>
          )}
          <button className="btn btn-dark" onClick={() => window.print()}>
            🖨 Print View
          </button>
        </div>
      </div>

      {/* Printable Invoice Sheet */}
      <div className="card shadow-sm p-4 p-md-5 bg-white border">
        {/* Header */}
        <div className="row justify-content-between align-items-start mb-4">
          <div className="col-6">
            <h2 className="fw-bold text-dark mb-1">BRIGHTLOOP SMS</h2>
            <p className="text-muted small mb-0">Brightloop Software Inc.</p>
            <p className="text-muted small">Tax ID: GSTIN29AAAAA0000A1Z5</p>
          </div>
          <div className="col-6 text-end">
            <h3 className="fw-bold mb-1">{invoice.number}</h3>
            <span className={`badge bg-${invoice.status === 'paid' ? 'success' : invoice.status === 'cancelled' ? 'dark' : 'secondary'} fs-6`}>
              {invoice.status.toUpperCase()}
            </span>
            <div className="text-muted small mt-2">
              <span className="text-muted">Security Identifier:</span> <code className="small">{invoice.uuid}</code>
            </div>
          </div>
        </div>

        <hr />

        {/* Bill To & Details */}
        <div className="row my-4">
          <div className="col-md-6 mb-3">
            <h6 className="text-muted text-uppercase fw-bold small">Billed To:</h6>
            <h5 className="fw-bold mb-1">{invoice.customer_name}</h5>
            <p className="text-muted mb-0">{invoice.customer_email || 'customer@brightloop.local'}</p>
            <p className="text-muted small">Subscription: <code>{invoice.subscription_number}</code></p>
          </div>
          <div className="col-md-6 text-md-end mb-3">
            <h6 className="text-muted text-uppercase fw-bold small">Invoice Details:</h6>
            <p className="mb-1"><strong>Period:</strong> {invoice.period_start} to {invoice.period_end}</p>
            <p className="mb-1"><strong>Due Date:</strong> {invoice.due_date || 'Due upon receipt'}</p>
            <p className="mb-0"><strong>Issued On:</strong> {new Date(invoice.created_at).toLocaleDateString()}</p>
          </div>
        </div>

        {/* Line Items Table */}
        <div className="table-responsive my-3">
          <table className="table table-bordered align-middle">
            <thead className="table-light">
              <tr>
                <th>Description</th>
                <th className="text-center" style={{ width: 80 }}>Qty</th>
                <th className="text-end" style={{ width: 140 }}>Unit Price (₹)</th>
                <th className="text-end" style={{ width: 120 }}>Discount</th>
                <th className="text-end" style={{ width: 100 }}>Tax Rate</th>
                <th className="text-end" style={{ width: 140 }}>Total (₹)</th>
              </tr>
            </thead>
            <tbody>
              {invoice.lines.map((line) => (
                <tr key={line.id}>
                  <td>{line.description}</td>
                  <td className="text-center">{line.quantity}</td>
                  <td className="text-end">{Number(line.unit_price).toLocaleString()}</td>
                  <td className="text-end text-success">
                    {Number(line.discount_amount) > 0 ? `-₹${Number(line.discount_amount).toLocaleString()}` : '—'}
                  </td>
                  <td className="text-end">{line.tax_rate}%</td>
                  <td className="text-end fw-semibold">₹{Number(line.line_total).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Financial Summary Calculation Breakdown */}
        <div className="row justify-content-end my-3">
          <div className="col-md-5">
            <div className="bg-light p-3 rounded">
              <div className="d-flex justify-content-between mb-2">
                <span className="text-muted">Subtotal:</span>
                <span className="fw-semibold">₹{Number(invoice.subtotal).toLocaleString()}</span>
              </div>
              {Number(invoice.discount_total) > 0 && (
                <div className="d-flex justify-content-between mb-2 text-success">
                  <span>Discount:</span>
                  <span>-₹{Number(invoice.discount_total).toLocaleString()}</span>
                </div>
              )}
              <div className="d-flex justify-content-between mb-2">
                <span className="text-muted">Tax (GST):</span>
                <span>₹{Number(invoice.tax_total).toLocaleString()}</span>
              </div>
              <hr />
              <div className="d-flex justify-content-between mb-2">
                <span className="fw-bold fs-5">Total:</span>
                <span className="fw-bold fs-5">₹{Number(invoice.total).toLocaleString()}</span>
              </div>
              <div className="d-flex justify-content-between mb-2 text-success">
                <span>Total Paid:</span>
                <span className="fw-semibold">₹{Number(invoice.total_paid).toLocaleString()}</span>
              </div>
              <div className="d-flex justify-content-between text-danger pt-2 border-top">
                <span className="fw-bold">Balance Due:</span>
                <span className="fw-bold fs-5">₹{Number(invoice.balance_due).toLocaleString()}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Payments Recorded */}
        {invoice.payments?.length > 0 && (
          <div className="mt-4">
            <h6 className="fw-bold text-uppercase small text-muted">Recorded Payments</h6>
            <table className="table table-sm table-bordered">
              <thead className="table-light">
                <tr>
                  <th>Date</th>
                  <th>Method</th>
                  <th>Reference</th>
                  <th>Recorded By</th>
                  <th className="text-end">Amount</th>
                </tr>
              </thead>
              <tbody>
                {invoice.payments.map((p) => (
                  <tr key={p.id}>
                    <td>{p.payment_date}</td>
                    <td>{p.method}</td>
                    <td>{p.reference || '—'}</td>
                    <td>{p.recorded_by_name || 'Staff'}</td>
                    <td className="text-end fw-semibold text-success">₹{Number(p.amount).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Status History Timeline (Audit Trail) */}
        {invoice.status_history?.length > 0 && (
          <div className="mt-4 pt-3 border-top d-print-none">
            <h6 className="fw-bold text-uppercase small text-muted">Audit History</h6>
            <ul className="list-unstyled small text-muted mb-0">
              {invoice.status_history.map((h) => (
                <li key={h.id} className="mb-1">
                  ⏱ <strong>{new Date(h.changed_at).toLocaleString()}:</strong> Status changed to{' '}
                  <span className="badge bg-secondary">{h.to_status}</span> by{' '}
                  {h.changed_by_name || 'System'}{' '}
                  {h.note && <em>({h.note})</em>}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Record Payment Modal */}
      {showPayModal && (
        <div className="modal show d-block" style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}>
          <div className="modal-dialog">
            <div className="modal-content">
              <form onSubmit={handleRecordPayment}>
                <div className="modal-header">
                  <h5 className="modal-title fw-bold">Record Payment for {invoice.number}</h5>
                  <button type="button" className="btn-close" onClick={() => setShowPayModal(false)} />
                </div>
                <div className="modal-body">
                  <div className="alert alert-info py-2 small mb-3">
                    Current Balance Due: <strong>₹{Number(invoice.balance_due).toLocaleString()}</strong>
                  </div>
                  <div className="mb-3">
                    <label className="form-label">Payment Amount (₹) *</label>
                    <input
                      type="number"
                      step="0.01"
                      max={invoice.balance_due}
                      required
                      className="form-control"
                      value={payAmount}
                      onChange={(e) => setPayAmount(e.target.value)}
                    />
                  </div>
                  <div className="mb-3">
                    <label className="form-label">Payment Date *</label>
                    <input
                      type="date"
                      required
                      className="form-control"
                      value={payDate}
                      onChange={(e) => setPayDate(e.target.value)}
                    />
                  </div>
                  <div className="mb-3">
                    <label className="form-label">Payment Method</label>
                    <select
                      className="form-select"
                      value={payMethod}
                      onChange={(e) => setPayMethod(e.target.value)}
                    >
                      <option value="bank_transfer">Bank Transfer (NEFT/RTGS/IMPS)</option>
                      <option value="cheque">Cheque</option>
                      <option value="cash">Cash</option>
                      <option value="upi">UPI / Online</option>
                    </select>
                  </div>
                  <div className="mb-3">
                    <label className="form-label">Reference / UTR / Cheque #</label>
                    <input
                      type="text"
                      className="form-control"
                      value={payRef}
                      onChange={(e) => setPayRef(e.target.value)}
                      placeholder="e.g. UTR12345678"
                    />
                  </div>
                  <div className="mb-3">
                    <label className="form-label">Note</label>
                    <input
                      type="text"
                      className="form-control"
                      value={payNote}
                      onChange={(e) => setPayNote(e.target.value)}
                      placeholder="Optional remarks"
                    />
                  </div>
                </div>
                <div className="modal-footer">
                  <button type="button" className="btn btn-secondary" onClick={() => setShowPayModal(false)}>
                    Cancel
                  </button>
                  <button type="submit" className="btn btn-success" disabled={submittingPayment}>
                    {submittingPayment ? 'Saving...' : 'Confirm Payment'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

