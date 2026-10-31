/**
 * src/pages/portal/MyInvoicesPage.jsx — customer self-service
 */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { portalApi } from '../../api'

export default function MyInvoicesPage() {
  const [invoices, setInvoices] = useState([])
  const [error, setError]       = useState('')

  useEffect(() => {
    portalApi.myInvoices()
      .then(r => setInvoices(r.data))
      .catch(() => setError('Failed to load invoices.'))
  }, [])

  if (error) return <div className="alert alert-danger">{error}</div>

  return (
    <>
      <h3 className="mb-4">My Invoices</h3>
      <div className="table-responsive">
        <table className="table table-hover align-middle">
          <thead className="table-dark">
            <tr>
              <th>Invoice #</th>
              <th>Period</th>
              <th>Total (₹)</th>
              <th>Balance Due (₹)</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {invoices.length === 0 && (
              <tr><td colSpan={5} className="text-center text-muted">No invoices found.</td></tr>
            )}
            {invoices.map(inv => (
              <tr key={inv.uuid || inv.id}>
                <td>
                  <Link to={`/billing/invoices/${inv.uuid}`} className="fw-bold text-decoration-none">
                    <code>{inv.number}</code>
                  </Link>
                </td>
                <td>{inv.period_start} → {inv.period_end}</td>
                <td>{Number(inv.total).toLocaleString()}</td>
                <td>{Number(inv.balance_due).toLocaleString()}</td>
                <td><span className="badge bg-secondary">{inv.status}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

