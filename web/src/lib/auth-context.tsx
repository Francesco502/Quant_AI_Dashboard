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
  const [user, setUser] = useState<string | null>(() =>
    typeof window === "undefined" ? null : localStorage.getItem("user")
  )
  const [token, setToken] = useState<string | null>(() =>
    typeof window === "undefined" ? null : localStorage.getItem("token")
  )
  const router = useRouter()
  const pathname = usePathname()

  useEffect(() => {
    // Protect routes
    const publicRoutes = ["/login", "/register"]
    const isPublic = publicRoutes.includes(pathname)

    if (!token && !isPublic) {
      router.push("/login")
    }
  }, [token, pathname, router])

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

  return (
    <AuthContext.Provider value={{ user, token, login, logout, isAuthenticated: !!token }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
