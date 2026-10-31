/**
 * src/pages/SubscriptionsPage.jsx
 */

import { useEffect, useState } from 'react'
import { subscriptionsApi } from '../api'

const STATUS_BADGE = {
  active: 'success',
  draft: 'secondary',
  paused: 'warning',
  closed: 'danger',
}

export default function SubscriptionsPage() {
  const [subs, setSubs] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    subscriptionsApi.list()
      .then(r => setSubs(r.data.results ?? r.data))
      .catch(() => setError('Failed to load subscriptions.'))
  }, [])

  if (error) return <div className="alert alert-danger">{error}</div>

  return (
    <>
      <h3 className="mb-4">Subscriptions</h3>
      <div className="table-responsive">
        <table className="table table-hover align-middle">
          <thead className="table-dark">
            <tr>
              <th>Number</th>
              <th>Customer</th>
              <th>Status</th>
              <th>Start Date</th>
              <th>Next Billing</th>
            </tr>
          </thead>
          <tbody>
            {subs.length === 0 && (
              <tr><td colSpan={5} className="text-center text-muted">No subscriptions yet.</td></tr>
            )}
            {subs.map(s => (
              <tr key={s.id}>
                <td><code>{s.number}</code></td>
                <td>{s.customer_name}</td>
                <td>
                  <span className={`badge bg-${STATUS_BADGE[s.status] ?? 'secondary'}`}>
                    {s.status}
                  </span>
                </td>
                <td>{s.start_date}</td>
                <td>{s.next_billing_date ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

