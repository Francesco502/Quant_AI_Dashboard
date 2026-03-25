"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { motion } from "framer-motion"
import { Lock, User } from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import { getEffectiveApiBaseUrl } from "@/lib/api"
import { SONG_COLORS } from "@/lib/chart-theme"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

export default function LoginPage() {
  const { isAuthenticated, login } = useAuth()
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const router = useRouter()

  useEffect(() => {
    if (isAuthenticated) {
      router.replace("/")
    }
  }, [isAuthenticated, router])

  const handleLogin = async (event: React.FormEvent) => {
    event.preventDefault()
    setLoading(true)
    setError("")

    try {
      const formData = new URLSearchParams()
      formData.append("username", username)
      formData.append("password", password)
      const apiBaseUrl = getEffectiveApiBaseUrl()

      const response = await fetch(`${apiBaseUrl}/auth/token`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: formData,
      })

      if (!response.ok) {
        if (response.status === 401) {
          setError("用户名或密码不正确")
          return
        }
        if (response.status >= 500) {
          setError("服务暂时不可用，请稍后再试。")
          return
        }
        const payload = (await response.json().catch(() => ({}))) as { detail?: string }
        setError(payload.detail ?? "登录失败")
        return
      }

      const data = (await response.json()) as { access_token: string }
      let resolvedUsername = username
      let resolvedRole: string | undefined

      try {
        const meResponse = await fetch(`${apiBaseUrl}/auth/me`, {
          headers: {
            Authorization: `Bearer ${data.access_token}`,
          },
        })

        if (meResponse.ok) {
          const profile = (await meResponse.json()) as { username?: string; role?: string }
          resolvedUsername = profile.username || username
          resolvedRole = profile.role
        }
      } catch {
        // Fall back to the submitted username when profile hydration is temporarily unavailable.
      }

      login(data.access_token, resolvedUsername, resolvedRole)
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : ""
      const isNetworkError = /fetch|network|connection|load/i.test(message)
      setError(
        isNetworkError
          ? `无法连接到接口服务：${getEffectiveApiBaseUrl()}`
          : "用户名或密码不正确"
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
        <div className="glass-card rounded-[30px] p-8">
          <div className="mb-8 text-center">
            <div className="mx-auto mb-4 flex h-11 w-11 items-center justify-center rounded-[18px] border border-[#8E734D]/18 bg-[linear-gradient(145deg,rgba(252,249,244,0.98),rgba(240,232,220,0.96))]">
              <span className="text-sm font-semibold tracking-[-0.08em] text-[#7C5B3C]">量</span>
            </div>
            <h1 className="mb-1 text-lg font-semibold tracking-[-0.02em] text-foreground/90">登录研习台</h1>
            <p className="text-[13px] leading-6 text-foreground/40">登录后即可进入研究、执行、资产与系统工作区。</p>
          </div>

          <form onSubmit={handleLogin} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="username">用户名</Label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-foreground/25" />
                <Input
                  id="username"
                  placeholder="admin"
                  className="pl-9"
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  autoComplete="username"
                  required
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="password">密码</Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-foreground/25" />
                <Input
                  id="password"
                  type="password"
                  placeholder="••••••••"
                  className="pl-9"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete="current-password"
                  required
                />
              </div>
            </div>

            {error && (
              <motion.div
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-lg p-2.5 text-center text-[12px]"
                style={{ backgroundColor: "rgba(182, 69, 60, 0.08)", color: SONG_COLORS.negative }}
              >
                {error}
              </motion.div>
            )}

            <Button type="submit" className="mt-2 w-full" disabled={loading}>
              {loading ? "正在登录..." : "登录"}
            </Button>

            <div className="mt-4 space-y-2 text-center text-[12px] text-foreground/35">
              <div>
                还没有账户？{" "}
                <Link href="/register" className="font-medium text-foreground/60 transition-colors hover:text-foreground/80">
                  去注册
                </Link>
              </div>
              <div className="text-foreground/20">请使用已配置的账户凭据登录，本页仅作为学习与测试入口。</div>
            </div>
          </form>
        </div>
      </motion.div>
    </div>
  )
}
