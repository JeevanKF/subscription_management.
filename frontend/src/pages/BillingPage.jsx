/**
 * src/pages/BillingPage.jsx
 * Unified Billing Console:
 * - Tab 1: Invoices List (Search, Status Filter, Overdue Filter, CSV Export, UUID Link)
 * - Tab 2: Billing Run (Preview Dry-run, Date picker, One-click Run, Result Summary)
 * - Tab 3: Discounts (Rules CRUD, Usage limits)
 */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { billingApi } from '../api'

const STATUS_BADGE = {
  draft: 'secondary',
  confirmed: 'primary',
  sent: 'info',
  paid: 'success',
  overdue: 'danger',
  cancelled: 'dark',
}

export default function BillingPage() {
  const [activeTab, setActiveTab] = useState('invoices')

  // Invoices Tab state
  const [invoices, setInvoices] = useState([])
  const [statusFilter, setStatusFilter] = useState('')
  const [overdueOnly, setOverdueOnly] = useState(false)
  const [search, setSearch] = useState('')
  const [loadingInvoices, setLoadingInvoices] = useState(false)

  // Billing Run Tab state
  const [targetDate, setTargetDate] = useState(() => new Date().toISOString().split('T')[0])
  const [previewResult, setPreviewResult] = useState(null)
  const [runResult, setRunResult] = useState(null)
  const [runningBilling, setRunningBilling] = useState(false)

  // Discounts Tab state
  const [discounts, setDiscounts] = useState([])
  const [showDiscountModal, setShowDiscountModal] = useState(false)
  const [newDisc, setNewDisc] = useState({
    code: '',
    name: '',
    discount_type: 'percent',
    value: '',
    scope: 'all',
    usage_limit: '',
  })

  // Load Invoices
  useEffect(() => {
    if (activeTab === 'invoices') {
      loadInvoices()
    } else if (activeTab === 'discounts') {
      loadDiscounts()
    }
  }, [activeTab, statusFilter, overdueOnly])

  async function loadInvoices() {
    setLoadingInvoices(true)
    try {
      const params = {}
      if (statusFilter) params.status = statusFilter
      if (overdueOnly) params.overdue = 'true'
      if (search) params.search = search
      const res = await billingApi.listInvoices(params)
      setInvoices(res.data.results ?? res.data)
    } catch (_) {}
    setLoadingInvoices(false)
  }

  async function loadDiscounts() {
    try {
      const res = await billingApi.listDiscounts()
      setDiscounts(res.data.results ?? res.data)
    } catch (_) {}
  }

  async function handlePreview() {
    setRunningBilling(true)
    setRunResult(null)
    try {
      const res = await billingApi.previewBilling(targetDate)
      setPreviewResult(res.data)
    } catch (err) {
      alert(err.response?.data?.detail || 'Preview failed')
    }
    setRunningBilling(false)
  }

  async function handleExecuteRun() {
    if (!window.confirm('Execute billing run? Invoices will be generated and subscriptions advanced.')) return
    setRunningBilling(true)
    try {
      const res = await billingApi.executeBillingRun({ target_date: targetDate, dry_run: false })
      setRunResult(res.data)
      setPreviewResult(null)
      loadInvoices()
    } catch (err) {
      alert(err.response?.data?.detail || 'Billing run failed')
    }
    setRunningBilling(false)
  }

  async function handleCreateDiscount(e) {
    e.preventDefault()
    try {
      const payload = {
        ...newDisc,
        value: Number(newDisc.value),
        usage_limit: newDisc.usage_limit ? Number(newDisc.usage_limit) : null,
      }
      await billingApi.createDiscount(payload)
      setShowDiscountModal(false)
      setNewDisc({ code: '', name: '', discount_type: 'percent', value: '', scope: 'all', usage_limit: '' })
      loadDiscounts()
    } catch (err) {
      alert(JSON.stringify(err.response?.data || 'Failed to create discount'))
    }
  }

  return (
    <div className="container-fluid py-2">
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h3 className="fw-bold mb-0">Billing & Receivables</h3>
        <div>
          <a href="/api/billing/invoices/export/" className="btn btn-outline-secondary me-2">
            ⬇ Export Invoices CSV
          </a>
          <a href="/api/billing/payments/export/" className="btn btn-outline-secondary">
            ⬇ Export Payments CSV
          </a>
        </div>
      </div>

      {/* Tabs */}
      <ul className="nav nav-pills mb-4">
        <li className="nav-item">
          <button
            className={`nav-link ${activeTab === 'invoices' ? 'active' : ''}`}
            onClick={() => setActiveTab('invoices')}
          >
            Invoices
          </button>
        </li>
        <li className="nav-item">
          <button
            className={`nav-link ${activeTab === 'run' ? 'active' : ''}`}
            onClick={() => setActiveTab('run')}
          >
            Run Billing Engine
          </button>
        </li>
        <li className="nav-item">
          <button
            className={`nav-link ${activeTab === 'discounts' ? 'active' : ''}`}
            onClick={() => setActiveTab('discounts')}
          >
            Discount Rules
          </button>
        </li>
      </ul>

      {/* TAB 1: INVOICES */}
      {activeTab === 'invoices' && (
        <>
          <div className="card shadow-sm mb-4">
            <div className="card-body">
              <div className="row g-2 align-items-center">
                <div className="col-md-4">
                  <input
                    type="text"
                    className="form-control"
                    placeholder="Search by invoice # or customer..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && loadInvoices()}
                  />
                </div>
                <div className="col-md-3">
                  <select
                    className="form-select"
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                  >
                    <option value="">All Statuses</option>
                    <option value="draft">Draft</option>
                    <option value="confirmed">Confirmed</option>
                    <option value="sent">Sent</option>
                    <option value="paid">Paid</option>
                    <option value="overdue">Overdue</option>
                    <option value="cancelled">Cancelled</option>
                  </select>
                </div>
                <div className="col-md-3">
                  <div className="form-check">
                    <input
                      type="checkbox"
                      className="form-check-input"
                      id="overdueCheck"
                      checked={overdueOnly}
                      onChange={(e) => setOverdueOnly(e.target.checked)}
                    />
                    <label className="form-check-label fw-semibold text-danger" htmlFor="overdueCheck">
                      Show Overdue Only
                    </label>
                  </div>
                </div>
                <div className="col-md-2 text-end">
                  <button className="btn btn-dark w-100" onClick={loadInvoices}>
                    Filter
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div className="card shadow-sm">
            <div className="table-responsive">
              <table className="table table-hover align-middle mb-0">
                <thead className="table-light">
                  <tr>
                    <th>Invoice #</th>
                    <th>Customer</th>
                    <th>Subscription</th>
                    <th>Period</th>
                    <th>Due Date</th>
                    <th>Status</th>
                    <th className="text-end">Total (₹)</th>
                    <th className="text-end">Balance (₹)</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {loadingInvoices ? (
                    <tr><td colSpan="9" className="text-center py-4">Loading invoices...</td></tr>
                  ) : invoices.length === 0 ? (
                    <tr><td colSpan="9" className="text-center text-muted py-4">No invoices found.</td></tr>
                  ) : (
                    invoices.map((inv) => (
                      <tr key={inv.uuid}>
                        <td>
                          {/* Secure unguessable UUID routing */}
                          <Link to={`/billing/invoices/${inv.uuid}`} className="fw-bold text-decoration-none">
                            <code>{inv.number}</code>
                          </Link>
                        </td>
                        <td>{inv.customer_name}</td>
                        <td><code>{inv.subscription_number}</code></td>
                        <td><small>{inv.period_start} → {inv.period_end}</small></td>
                        <td><small>{inv.due_date || '—'}</small></td>
                        <td>
                          <span className={`badge bg-${STATUS_BADGE[inv.status] || 'secondary'}`}>
                            {inv.status}
                          </span>
                        </td>
                        <td className="text-end fw-semibold">₹{Number(inv.total).toLocaleString()}</td>
                        <td className="text-end fw-bold text-danger">
                          ₹{Number(inv.balance_due).toLocaleString()}
                        </td>
                        <td>
                          <Link to={`/billing/invoices/${inv.uuid}`} className="btn btn-sm btn-outline-primary">
                            View / Pay
                          </Link>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* TAB 2: BILLING RUN */}
      {activeTab === 'run' && (
        <div className="row">
          <div className="col-md-6">
            <div className="card shadow-sm mb-4">
              <div className="card-header bg-dark text-white fw-bold">
                ⚡ Execute Billing Run
              </div>
              <div className="card-body">
                <p className="text-muted small">
                  Identifies all active subscriptions due on or before target date, calculates lines, tax, and generates invoices with zero duplication guarantee.
                </p>
                <div className="mb-3">
                  <label className="form-label fw-semibold">Target Billing Date</label>
                  <input
                    type="date"
                    className="form-control"
                    value={targetDate}
                    onChange={(e) => setTargetDate(e.target.value)}
                  />
                </div>
                <div className="d-flex gap-2">
                  <button
                    className="btn btn-outline-primary flex-fill"
                    onClick={handlePreview}
                    disabled={runningBilling}
                  >
                    🔍 Dry-Run Preview
                  </button>
                  <button
                    className="btn btn-primary flex-fill"
                    onClick={handleExecuteRun}
                    disabled={runningBilling}
                  >
                    🚀 Run Billing Now
                  </button>
                </div>
              </div>
            </div>

            {runResult && (
              <div className="alert alert-success shadow-sm">
                <h5 className="alert-heading fw-bold">Billing Completed Successfully!</h5>
                <p className="mb-1"><strong>Invoices Created:</strong> {runResult.created_count}</p>
                <p className="mb-1"><strong>Skipped (Already billed):</strong> {runResult.skipped_count}</p>
                <p className="mb-0"><strong>Total Invoiced:</strong> ₹{Number(runResult.total_amount).toLocaleString()}</p>
              </div>
            )}
          </div>

          <div className="col-md-6">
            {previewResult && (
              <div className="card shadow-sm">
                <div className="card-header bg-light fw-bold">
                  Dry-Run Preview Result ({previewResult.created_count} Subscriptions Due)
                </div>
                <div className="card-body">
                  <p className="mb-2"><strong>Total To Bill:</strong> ₹{Number(previewResult.total_amount).toLocaleString()}</p>
                  <div className="table-responsive" style={{ maxHeight: 350 }}>
                    <table className="table table-sm table-bordered">
                      <thead>
                        <tr>
                          <th>Sub #</th>
                          <th>Customer</th>
                          <th>Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {previewResult.invoices.map((p, idx) => (
                          <tr key={idx}>
                            <td><code>{p.subscription_number}</code></td>
                            <td>{p.customer}</td>
                            <td>₹{Number(p.total).toLocaleString()}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 3: DISCOUNTS */}
      {activeTab === 'discounts' && (
        <div className="card shadow-sm">
          <div className="card-header bg-light d-flex justify-content-between align-items-center">
            <span className="fw-bold">Active Discount Rules</span>
            <button className="btn btn-sm btn-dark" onClick={() => setShowDiscountModal(true)}>
              + Add Discount Rule
            </button>
          </div>
          <div className="table-responsive">
            <table className="table table-hover align-middle mb-0">
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Value</th>
                  <th>Scope</th>
                  <th>Usage (Used / Limit)</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {discounts.length === 0 ? (
                  <tr><td colSpan="7" className="text-center text-muted py-4">No discount rules configured.</td></tr>
                ) : (
                  discounts.map((d) => (
                    <tr key={d.id}>
                      <td><code>{d.code}</code></td>
                      <td>{d.name || '—'}</td>
                      <td>{d.discount_type === 'percent' ? 'Percentage' : 'Fixed'}</td>
                      <td className="fw-bold">{d.discount_type === 'percent' ? `${d.value}%` : `₹${d.value}`}</td>
                      <td><span className="badge bg-light text-dark border">{d.scope}</span></td>
                      <td>{d.times_used} / {d.usage_limit || '∞'}</td>
                      <td>
                        <span className={`badge bg-${d.is_available ? 'success' : 'secondary'}`}>
                          {d.is_available ? 'Available' : 'Expired / Reached'}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* New Discount Modal */}
      {showDiscountModal && (
        <div className="modal show d-block" style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}>
          <div className="modal-dialog">
            <div className="modal-content">
              <form onSubmit={handleCreateDiscount}>
                <div className="modal-header">
                  <h5 className="modal-title fw-bold">Create Discount Rule</h5>
                  <button type="button" className="btn-close" onClick={() => setShowDiscountModal(false)} />
                </div>
                <div className="modal-body">
                  <div className="mb-3">
                    <label className="form-label">Code *</label>
                    <input
                      className="form-control text-uppercase"
                      required
                      value={newDisc.code}
                      onChange={(e) => setNewDisc({ ...newDisc, code: e.target.value.toUpperCase() })}
                      placeholder="e.g. FESTIVE20"
                    />
                  </div>
                  <div className="mb-3">
                    <label className="form-label">Name</label>
                    <input
                      className="form-control"
                      value={newDisc.name}
                      onChange={(e) => setNewDisc({ ...newDisc, name: e.target.value })}
                      placeholder="e.g. Festive Discount"
                    />
                  </div>
                  <div className="row g-2 mb-3">
                    <div className="col-6">
                      <label className="form-label">Type</label>
                      <select
                        className="form-select"
                        value={newDisc.discount_type}
                        onChange={(e) => setNewDisc({ ...newDisc, discount_type: e.target.value })}
                      >
                        <option value="percent">Percentage (%)</option>
                        <option value="fixed">Fixed Amount (₹)</option>
                      </select>
                    </div>
                    <div className="col-6">
                      <label className="form-label">Value *</label>
                      <input
                        type="number"
                        step="0.01"
                        required
                        className="form-control"
                        value={newDisc.value}
                        onChange={(e) => setNewDisc({ ...newDisc, value: e.target.value })}
                        placeholder="e.g. 10.00"
                      />
                    </div>
                  </div>
                  <div className="mb-3">
                    <label className="form-label">Scope</label>
                    <select
                      className="form-select"
                      value={newDisc.scope}
                      onChange={(e) => setNewDisc({ ...newDisc, scope: e.target.value })}
                    >
                      <option value="all">All Subscriptions</option>
                      <option value="specific_product">Specific Product</option>
                    </select>
                  </div>
                  <div className="mb-3">
                    <label className="form-label">Usage Limit (blank for unlimited)</label>
                    <input
                      type="number"
                      className="form-control"
                      value={newDisc.usage_limit}
                      onChange={(e) => setNewDisc({ ...newDisc, usage_limit: e.target.value })}
                      placeholder="e.g. 100"
                    />
                  </div>
                </div>
                <div className="modal-footer">
                  <button type="button" className="btn btn-secondary" onClick={() => setShowDiscountModal(false)}>
                    Cancel
                  </button>
                  <button type="submit" className="btn btn-primary">
                    Create Discount
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
