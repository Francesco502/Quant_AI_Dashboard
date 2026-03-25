"use client"

import { createContext, useCallback, useContext, useEffect, useState } from "react"
import { usePathname, useRouter } from "next/navigation"

import { fetchApi } from "@/lib/api"

interface UserInfo {
  username: string
  role: string
}

interface AuthContextType {
  user: UserInfo | null
  token: string | null
  login: (token: string, username: string, role?: string) => void
  logout: () => void
  isAuthenticated: boolean
  loadUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  token: null,
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

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(() => readStoredUser())
  const [token, setToken] = useState<string | null>(() =>
    typeof window === "undefined" ? null : localStorage.getItem("token")
  )

  const router = useRouter()
  const pathname = usePathname()

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
    }
  }, [token])

  useEffect(() => {
    const publicRoutes = new Set(["/login", "/register"])
    const isPublic = publicRoutes.has(pathname)

    if (!token) {
      if (!isPublic) {
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
        if (!cancelled) {
          console.error("Failed to hydrate user info:", error)
        }
      }
    })()

    return () => {
      cancelled = true
    }
  }, [pathname, router, token, user])

  const login = (newToken: string, username: string, role?: string) => {
    localStorage.setItem("token", newToken)
    localStorage.setItem("user", username)
    localStorage.setItem("userRole", role || "viewer")
    setToken(newToken)
    setUser({ username, role: role || "viewer" })
    router.push("/")
  }

  const logout = () => {
    localStorage.removeItem("token")
    localStorage.removeItem("user")
    localStorage.removeItem("userRole")
    setToken(null)
    setUser(null)
    router.push("/login")
  }

  return (
    <AuthContext.Provider value={{ user, token, login, logout, isAuthenticated: !!token, loadUser }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
