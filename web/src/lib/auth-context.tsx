"use client"

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react"
import { usePathname, useRouter } from "next/navigation"

import { fetchApi } from "@/lib/api"
import { toast } from "sonner"

interface UserInfo {
  username: string
  role: string
}

interface AuthContextType {
  user: UserInfo | null
  token: string | null
  isReady: boolean
  login: (token: string, username: string, role?: string) => void
  logout: () => void
  isAuthenticated: boolean
  loadUser: () => Promise<void>
}

const PUBLIC_ROUTES = new Set(["/login", "/register"])

const AuthContext = createContext<AuthContextType>({
  user: null,
  token: null,
  isReady: false,
  login: () => {},
  logout: () => {},
  isAuthenticated: false,
  loadUser: async () => {},
})

function readStoredUser(): UserInfo | null {
  if (typeof window === "undefined") return null

  const username = localStorage.getItem("user")
  if (!username) return null

  return {
    username,
    role: localStorage.getItem("userRole") || "viewer",
  }
}

function clearStoredAuth() {
  if (typeof window === "undefined") return
  localStorage.removeItem("token")
  localStorage.removeItem("user")
  localStorage.removeItem("userRole")
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [isReady, setIsReady] = useState(false)

  const router = useRouter()
  const pathname = usePathname()

  useEffect(() => {
    if (typeof window === "undefined") return

    let cancelled = false
    window.queueMicrotask(() => {
      if (cancelled) return
      setToken(localStorage.getItem("token"))
      setUser(readStoredUser())
      setIsReady(true)
    })

    const handleStorage = () => {
      setToken(localStorage.getItem("token"))
      setUser(readStoredUser())
    }

    window.addEventListener("storage", handleStorage)
    return () => {
      cancelled = true
      window.removeEventListener("storage", handleStorage)
    }
  }, [])

  const loadUser = useCallback(async () => {
    if (typeof window === "undefined" || !token) return

    try {
      const data = await fetchApi<{ username: string; role: string }>("/auth/me")
      const nextUser = { username: data.username, role: data.role }
      localStorage.setItem("user", data.username)
      localStorage.setItem("userRole", data.role)
      setUser(nextUser)
    } catch (error) {
      console.error("Failed to load user info:", error)
      toast.error("加载用户信息失败")
      clearStoredAuth()
      setToken(null)
      setUser(null)
    }
  }, [token])

  useEffect(() => {
    if (!isReady) return

    const isPublicRoute = PUBLIC_ROUTES.has(pathname)

    if (!token) {
      if (!isPublicRoute) {
        router.replace("/login")
      }
      return
    }

    if (user) return

    let cancelled = false

    void (async () => {
      try {
        const data = await fetchApi<{ username: string; role: string }>("/auth/me")
        if (cancelled) return

        const nextUser = { username: data.username, role: data.role }
        localStorage.setItem("user", data.username)
        localStorage.setItem("userRole", data.role)
        setUser(nextUser)
      } catch (error) {
        if (cancelled) return

        console.error("Failed to hydrate user info:", error)
        toast.error("用户验证失败，请重新登录")
        clearStoredAuth()
        setToken(null)
        setUser(null)

        if (!isPublicRoute) {
          router.replace("/login")
        }
      }
    })()

    return () => {
      cancelled = true
    }
  }, [isReady, pathname, router, token, user])

  const login = useCallback(
    (newToken: string, username: string, role?: string) => {
      if (typeof window === "undefined") return

      const nextRole = role || "viewer"
      localStorage.setItem("token", newToken)
      localStorage.setItem("user", username)
      localStorage.setItem("userRole", nextRole)
      setToken(newToken)
      setUser({ username, role: nextRole })
      router.replace("/")
    },
    [router],
  )

  const logout = useCallback(() => {
    clearStoredAuth()
    setToken(null)
    setUser(null)
    router.replace("/login")
  }, [router])

  const value = useMemo<AuthContextType>(
    () => ({
      user,
      token,
      isReady,
      login,
      logout,
      isAuthenticated: Boolean(token),
      loadUser,
    }),
    [isReady, loadUser, login, logout, token, user],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
