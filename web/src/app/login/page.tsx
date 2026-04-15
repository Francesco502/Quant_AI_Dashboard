"use client"

import { type FormEvent, useEffect, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { Lock, User } from "lucide-react"

import { useAuth } from "@/lib/auth-context"
import { getEffectiveApiBaseUrl } from "@/lib/api"
import { BRAND_LOGIN_TITLE, BRAND_NAME, BRAND_SUBTITLE } from "@/lib/brand"
import { SONG_COLORS } from "@/lib/chart-theme"
import { BrandMark } from "@/components/layout/brand-mark"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

export default function LoginPage() {
  const { isAuthenticated, isReady, login } = useAuth()
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const router = useRouter()

  useEffect(() => {
    if (isReady && isAuthenticated) {
      router.replace("/")
    }
  }, [isAuthenticated, isReady, router])

  const handleLogin = async () => {
    if (loading) return

    const trimmedUsername = username.trim()
    if (!trimmedUsername || !password) {
      setError("请输入用户名和密码。")
      return
    }

    setLoading(true)
    setError("")

    try {
      const formData = new URLSearchParams()
      formData.append("username", trimmedUsername)
      formData.append("password", password)
      const apiBaseUrl = getEffectiveApiBaseUrl()

      const response = await fetch(`${apiBaseUrl}/auth/token`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: formData,
      })

      if (!response.ok) {
        if (response.status === 401) {
          setError("用户名或密码不正确。")
          return
        }

        if (response.status >= 500) {
          setError("服务暂时不可用，请稍后重试。")
          return
        }

        const payload = (await response.json().catch(() => ({}))) as { detail?: string }
        setError(payload.detail ?? "登录失败，请稍后重试。")
        return
      }

      const data = (await response.json()) as { access_token: string }
      let resolvedUsername = trimmedUsername
      let resolvedRole: string | undefined

      try {
        const meResponse = await fetch(`${apiBaseUrl}/auth/me`, {
          headers: {
            Authorization: `Bearer ${data.access_token}`,
          },
        })

        if (meResponse.ok) {
          const profile = (await meResponse.json()) as { username?: string; role?: string }
          resolvedUsername = profile.username || trimmedUsername
          resolvedRole = profile.role
        }
      } catch {
        // Fall back to the submitted identity when profile hydration is temporarily unavailable.
      }

      login(data.access_token, resolvedUsername, resolvedRole)
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : ""
      const isNetworkError = /fetch|network|connection|load/i.test(message)

      setError(
        isNetworkError
          ? `无法连接到接口服务：${getEffectiveApiBaseUrl()}`
          : "登录失败，请检查网络后重试。",
      )
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    await handleLogin()
  }

  return (
    <div className="flex min-h-[calc(100vh-200px)] items-center justify-center">
      <div className="w-full max-w-sm">
        <div className="glass-card rounded-[30px] p-8">
          <div className="mb-8 text-center">
            <BrandMark className="mx-auto mb-4" />
            <h1 className="section-title mb-1">{BRAND_LOGIN_TITLE}</h1>
            <p className="text-[13px] leading-6 text-foreground/60">
              登录后即可进入研究、执行、资产与系统工作区。
            </p>
            <p className="mt-2 text-[12px] tracking-[0.12em] text-foreground/44">{BRAND_NAME} · {BRAND_SUBTITLE}</p>
          </div>

          <form className="space-y-4" aria-label="登录表单" onSubmit={handleSubmit}>
            <div className="space-y-1.5">
              <Label htmlFor="username">用户名</Label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-foreground/25" />
                <Input
                  id="username"
                  name="username"
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
                  name="password"
                  type="password"
                  placeholder="请输入密码"
                  className="pl-9"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete="current-password"
                  required
                />
              </div>
            </div>

            {error ? (
              <div
                className="rounded-lg p-2.5 text-center text-[12px]"
                style={{ backgroundColor: "rgba(182, 69, 60, 0.08)", color: SONG_COLORS.negative }}
              >
                {error}
              </div>
            ) : null}

            <Button type="submit" className="mt-2 w-full" disabled={loading}>
              {loading ? "正在登录…" : "登录"}
            </Button>

              <div className="mt-4 space-y-2 text-center text-[12px] text-foreground/35">
                <div>
                  还没有账户？{" "}
                <Link
                  href="/register"
                  className="font-medium text-foreground/60 transition-colors hover:text-foreground/80"
                >
                  去注册
                </Link>
              </div>
              <div className="text-foreground/20">
                 请使用已配置的账户凭据登录，本页仅作为个人研究与测试入口。
               </div>
             </div>
          </form>
        </div>
      </div>
    </div>
  )
}
