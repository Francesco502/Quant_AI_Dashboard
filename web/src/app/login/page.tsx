"use client"

import { useState } from "react"
import Link from "next/link"
import { motion } from "framer-motion"
import { Lock, User } from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import { API_BASE_URL } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

export default function LoginPage() {
  const { login } = useAuth()
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

  const handleLogin = async (event: React.FormEvent) => {
    event.preventDefault()
    setLoading(true)
    setError("")

    try {
      const formData = new URLSearchParams()
      formData.append("username", username)
      formData.append("password", password)

      const response = await fetch(`${API_BASE_URL}/auth/token`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: formData,
      })

      if (!response.ok) {
        if (response.status === 401) {
          setError("Invalid username or password")
          return
        }
        if (response.status >= 500) {
          setError("Service is temporarily unavailable. Please try again later.")
          return
        }
        const payload = (await response.json().catch(() => ({}))) as { detail?: string }
        setError(payload.detail ?? "Login failed")
        return
      }

      const data = (await response.json()) as { access_token: string }
      login(data.access_token, username)
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : ""
      const isNetworkError = /fetch|network|connection|load/i.test(message)
      setError(
        isNetworkError
          ? `Cannot connect to API server: ${API_BASE_URL}`
          : "Invalid username or password"
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-[calc(100vh-200px)] items-center justify-center">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        className="w-full max-w-sm"
      >
        <div className="glass-card rounded-2xl p-8">
          <div className="mb-8 text-center">
            <div className="mx-auto mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-foreground/90">
              <span className="text-sm font-bold text-background">Q</span>
            </div>
            <h1 className="mb-1 text-lg font-semibold tracking-[-0.02em] text-foreground/90">Login</h1>
            <p className="text-[13px] text-foreground/40">Sign in to Quant AI Dashboard</p>
          </div>

          <form onSubmit={handleLogin} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="username">Username</Label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-foreground/25" />
                <Input
                  id="username"
                  placeholder="admin"
                  className="pl-9"
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  required
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-foreground/25" />
                <Input
                  id="password"
                  type="password"
                  placeholder="••••••••"
                  className="pl-9"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                />
              </div>
            </div>

            {error && (
              <motion.div
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-lg bg-red-500/[0.06] p-2.5 text-center text-[12px] text-red-500/80"
              >
                {error}
              </motion.div>
            )}

            <Button type="submit" className="mt-2 w-full" disabled={loading}>
              {loading ? "Signing in..." : "Login"}
            </Button>

            <div className="mt-4 space-y-2 text-center text-[12px] text-foreground/35">
              <div>
                No account yet?{" "}
                <Link href="/register" className="font-medium text-foreground/60 transition-colors hover:text-foreground/80">
                  Register
                </Link>
              </div>
              <div className="text-foreground/20">Default: admin / admin123</div>
            </div>
          </form>
        </div>
      </motion.div>
    </div>
  )
}
