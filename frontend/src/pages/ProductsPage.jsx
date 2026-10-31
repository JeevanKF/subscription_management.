/**
 * src/pages/ProductsPage.jsx
 */

import { useEffect, useState } from 'react'
import { productsApi } from '../api'

export default function ProductsPage() {
  const [products, setProducts] = useState([])
  const [error, setError]       = useState('')

  useEffect(() => {
    productsApi.list()
      .then(r => setProducts(r.data.results ?? r.data))
      .catch(() => setError('Failed to load products.'))
  }, [])

  if (error) return <div className="alert alert-danger">{error}</div>

  return (
    <>
      <h3 className="mb-4">Products</h3>
      <div className="table-responsive">
        <table className="table table-hover align-middle">
          <thead className="table-dark">
            <tr>
              <th>#</th>
              <th>Name</th>
              <th>Plans</th>
              <th>Variants</th>
            </tr>
          </thead>
          <tbody>
            {products.length === 0 && (
              <tr><td colSpan={4} className="text-center text-muted">No products yet.</td></tr>
            )}
            {products.map(p => (
              <tr key={p.id}>
                <td>{p.id}</td>
                <td>{p.name}</td>
                <td>{p.plans?.length ?? 0}</td>
                <td>{p.variants?.length ?? 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

