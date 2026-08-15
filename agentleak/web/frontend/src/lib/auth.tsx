// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react"
import { ApiError, UNAUTHORIZED_EVENT, api, type User } from "@/lib/api"

interface AuthState {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, name?: string) => Promise<void>
  logout: () => Promise<void>
  refresh: () => Promise<void>
  setUser: (user: User | null) => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api
      .me()
      .then(setUser)
      .catch((e) => {
        // 401 simply means "not signed in" — anything else is unexpected.
        if (!(e instanceof ApiError) || e.status !== 401) console.error(e)
        setUser(null)
      })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    // Drop the user when any API call reports an expired session.
    const onUnauthorized = () => setUser((u) => (u ? null : u))
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    setUser(await api.login({ email, password }))
  }, [])

  const register = useCallback(async (email: string, password: string, name?: string) => {
    setUser(await api.register({ email, password, name }))
  }, [])

  const logout = useCallback(async () => {
    await api.logout().catch(() => {})
    setUser(null)
  }, [])

  const refresh = useCallback(async () => {
    try {
      setUser(await api.me())
    } catch (e) {
      if (!(e instanceof ApiError) || e.status !== 401) console.error(e)
      setUser(null)
    }
  }, [])

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, refresh, setUser }}>{children}</AuthContext.Provider>
  )
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider")
  return ctx
}
