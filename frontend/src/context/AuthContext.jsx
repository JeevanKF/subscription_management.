/**
 * src/context/AuthContext.jsx
 * Provides { user, token, login, logout } to the whole app.
 */

import { createContext, useContext, useState, useEffect } from 'react'
import { authApi } from '../api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser]   = useState(null)
  const [token, setToken] = useState(() => localStorage.getItem('token'))
  const [loading, setLoading] = useState(true)

  // On mount, restore the user from the stored token
  useEffect(() => {
    if (token) {
      authApi.getMe()
        .then(res => setUser(res.data))
        .catch(() => { localStorage.removeItem('token'); setToken(null) })
        .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
  }, [token])

  async function loginFn(username, password) {
    const res = await authApi.login(username, password)
    const { token: t, user: u } = res.data
    localStorage.setItem('token', t)
    setToken(t)
    setUser(u)
    return u
  }

  async function logoutFn() {
    try { await authApi.logout() } catch (_) {}
    localStorage.removeItem('token')
    setToken(null)
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, token, login: loginFn, logout: logoutFn, loading }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)

