/**
 * src/App.jsx — root router
 */

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import Navbar from './components/Navbar'

// Pages
import LoginPage            from './pages/LoginPage'
import DashboardPage        from './pages/DashboardPage'
import ProductsPage         from './pages/ProductsPage'
import SubscriptionsPage    from './pages/SubscriptionsPage'
import BillingPage          from './pages/BillingPage'
import InvoiceDetailPage    from './pages/InvoiceDetailPage'
import MySubscriptionsPage  from './pages/portal/MySubscriptionsPage'
import MyInvoicesPage       from './pages/portal/MyInvoicesPage'

function AppRoutes() {
  const { user } = useAuth()

  return (
    <>
      <Navbar />
      <div className="container mt-4">
        <Routes>
          {/* Public */}
          <Route path="/login" element={<LoginPage />} />

          {/* Role-based home redirect */}
          <Route
            path="/"
            element={
              user?.role === 'customer'
                ? <Navigate to="/portal/subscriptions" replace />
                : <Navigate to="/dashboard" replace />
            }
          />

          {/* Admin / Staff */}
          <Route path="/dashboard" element={
            <ProtectedRoute roles={['admin', 'staff']}>
              <DashboardPage />
            </ProtectedRoute>
          } />
          <Route path="/products" element={
            <ProtectedRoute roles={['admin', 'staff']}>
              <ProductsPage />
            </ProtectedRoute>
          } />
          <Route path="/subscriptions" element={
            <ProtectedRoute roles={['admin', 'staff']}>
              <SubscriptionsPage />
            </ProtectedRoute>
          } />
          <Route path="/billing" element={
            <ProtectedRoute roles={['admin', 'staff']}>
              <BillingPage />
            </ProtectedRoute>
          } />
          <Route path="/billing/invoices/:uuid" element={
            <ProtectedRoute roles={['admin', 'staff', 'customer']}>
              <InvoiceDetailPage />
            </ProtectedRoute>
          } />

          {/* Customer portal */}
          <Route path="/portal/subscriptions" element={
            <ProtectedRoute roles={['customer']}>
              <MySubscriptionsPage />
            </ProtectedRoute>
          } />
          <Route path="/portal/invoices" element={
            <ProtectedRoute roles={['customer']}>
              <MyInvoicesPage />
            </ProtectedRoute>
          } />

          <Route path="/unauthorized" element={
            <div className="alert alert-danger">You are not authorised to view this page.</div>
          } />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  )
}
