/**
 * src/pages/portal/MySubscriptionsPage.jsx — customer self-service
 */

import { useEffect, useState } from 'react'
import { portalApi } from '../../api'

export default function MySubscriptionsPage() {
  const [subs, setSubs] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    portalApi.mySubscriptions()
      .then(r => setSubs(r.data))
      .catch(() => setError('Failed to load subscriptions.'))
  }, [])

  if (error) return <div className="alert alert-danger">{error}</div>

  return (
    <>
      <h3 className="mb-4">My Subscriptions</h3>
      {subs.length === 0 ? (
        <p className="text-muted">You have no subscriptions.</p>
      ) : (
        <div className="row">
          {subs.map(s => (
            <div key={s.id} className="col-md-6 mb-3">
              <div className="card shadow-sm">
                <div className="card-body">
                  <h5 className="card-title">{s.number}</h5>
                  <p className="mb-1">
                    Status: <span className="badge bg-success">{s.status}</span>
                  </p>
                  <p className="mb-0 text-muted small">Started: {s.start_date}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  )
}

