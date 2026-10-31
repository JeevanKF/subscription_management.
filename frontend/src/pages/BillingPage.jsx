/**
 * src/pages/BillingPage.jsx
 */

import { useEffect, useState } from 'react'
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
  const [invoices, setInvoices] = useState([])
  const [error, setError]       = useState('')

  useEffect(() => {
    billingApi.listInvoices()
      .then(r => setInvoices(r.data.results ?? r.data))
      .catch(() => setError('Failed to load invoices.'))
  }, [])

  if (error) return <div className="alert alert-danger">{error}</div>

  return (
    <>
      <h3 className="mb-4">Invoices</h3>
      <div className="table-responsive">
        <table className="table table-hover align-middle">
          <thead className="table-dark">
            <tr>
              <th>Number</th>
              <th>Period</th>
              <th>Status</th>
              <th className="text-end">Total (₹)</th>
              <th className="text-end">Balance Due (₹)</th>
            </tr>
          </thead>
          <tbody>
            {invoices.length === 0 && (
              <tr><td colSpan={5} className="text-center text-muted">No invoices yet.</td></tr>
            )}
            {invoices.map(inv => (
              <tr key={inv.id}>
                <td><code>{inv.number}</code></td>
                <td>{inv.period_start} → {inv.period_end}</td>
                <td>
                  <span className={`badge bg-${STATUS_BADGE[inv.status] ?? 'secondary'}`}>
                    {inv.status}
                  </span>
                </td>
                <td className="text-end">{Number(inv.total).toLocaleString()}</td>
                <td className="text-end">{Number(inv.balance_due).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

