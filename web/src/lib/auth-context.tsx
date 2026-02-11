"use client"

import { createContext, useContext, useEffect, useState } from "react"
import { useRouter, usePathname } from "next/navigation"

interface AuthContextType {
  user: string | null
  token: string | null
  login: (token: string, username: string) => void
  logout: () => void
  isAuthenticated: boolean
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  token: null,
  login: () => {},
  logout: () => {},
  isAuthenticated: false,
})

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<string | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const router = useRouter()
  const pathname = usePathname()

  useEffect(() => {
    // Check localStorage on mount
    const storedToken = localStorage.getItem("token")
    const storedUser = localStorage.getItem("user")
    
    if (storedToken) {
      setToken(storedToken)
      setUser(storedUser || "User")
    }
    setLoading(false)
  }, [])

  useEffect(() => {
    if (loading) return

    // Protect routes
    const publicRoutes = ["/login", "/register"]
    const isPublic = publicRoutes.includes(pathname)

    if (!token && !isPublic) {
      router.push("/login")
    }
  }, [token, pathname, router, loading])

  const login = (newToken: string, newUser: string) => {
    localStorage.setItem("token", newToken)
    localStorage.setItem("user", newUser)
    setToken(newToken)
    setUser(newUser)
    router.push("/")
  }

  const logout = () => {
    localStorage.removeItem("token")
    localStorage.removeItem("user")
    setToken(null)
    setUser(null)
    router.push("/login")
  }

  if (loading) {
    return null // or a loading spinner
  }

  return (
    <AuthContext.Provider value={{ user, token, login, logout, isAuthenticated: !!token }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
