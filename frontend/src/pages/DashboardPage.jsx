/**
 * src/pages/DashboardPage.jsx
 * Finance overview — admin and staff only.
 */

import { useEffect, useState } from 'react'
import { dashboardApi } from '../api'

function StatCard({ label, value, sub }) {
  return (
    <div className="col-md-4">
      <div className="card text-center shadow-sm mb-3">
        <div className="card-body">
          <h2 className="display-6 fw-bold">{value ?? '—'}</h2>
          <p className="card-title fw-semibold">{label}</p>
          {sub && <small className="text-muted">{sub}</small>}
        </div>
      </div>
    </div>
  )
}

export default function DashboardPage() {
  const [data, setData]     = useState(null)
  const [error, setError]   = useState('')

  useEffect(() => {
    dashboardApi.getSummary()
      .then(r => setData(r.data))
      .catch(() => setError('Failed to load dashboard.'))
  }, [])

  if (error) return <div className="alert alert-danger">{error}</div>
  if (!data)  return <div className="text-center mt-5">Loading…</div>

  return (
    <>
      <h3 className="mb-4">Finance Dashboard</h3>
      <div className="row">
        <StatCard label="Active Subscriptions" value={data.subscriptions.active} />
        <StatCard label="Overdue Invoices"     value={data.invoices.overdue} />
        <StatCard
          label="Total Billed"
          value={`₹${Number(data.invoices.total_billed).toLocaleString()}`}
        />
        <StatCard
          label="Total Collected"
          value={`₹${Number(data.payments.total_collected).toLocaleString()}`}
        />
        <StatCard label="Total Subscriptions" value={data.subscriptions.total} />
        <StatCard label="Paused Subscriptions" value={data.subscriptions.paused} />
      </div>
    </>
  )
}

