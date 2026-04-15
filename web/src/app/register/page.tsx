"use client"

import { useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { Lock, User } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { BrandMark } from "@/components/layout/brand-mark"
import { getEffectiveApiBaseUrl } from "@/lib/api"
import { BRAND_NAME, BRAND_REGISTER_TITLE, BRAND_SUBTITLE } from "@/lib/brand"
import { SONG_COLORS } from "@/lib/chart-theme"

export default function RegisterPage() {
  const router = useRouter()
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [success, setSuccess] = useState(false)

  const handleRegister = async () => {
    if (loading) return

    setError("")

    if (username.length < 3) {
      setError("用户名至少 3 个字符")
      return
    }
    if (password.length < 6) {
      setError("密码至少 6 个字符")
      return
    }
    if (password !== confirmPassword) {
      setError("两次输入的密码不一致")
      return
    }

    setLoading(true)

    try {
      const res = await fetch(`${getEffectiveApiBaseUrl()}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      })

      const data = (await res.json().catch(() => ({}))) as { detail?: string }

      if (!res.ok) {
        throw new Error(data.detail || "注册失败")
      }

      setSuccess(true)
      window.setTimeout(() => router.push("/login"), 1200)
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "注册失败，请稍后重试"
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== "Enter") return
    event.preventDefault()
    void handleRegister()
  }

  return (
    <div className="flex min-h-[calc(100vh-200px)] items-center justify-center">
      <div className="w-full max-w-sm">
        <div className="glass-card rounded-2xl p-8">
          <div className="mb-8 text-center">
            <BrandMark className="mx-auto mb-4" iconClassName="h-6 w-6" />
            <h1 className="section-title mb-1">{BRAND_REGISTER_TITLE}</h1>
            <p className="text-[13px] text-foreground/60">注册新的 {BRAND_NAME} 账户</p>
            <p className="mt-2 text-[12px] tracking-[0.12em] text-foreground/44">{BRAND_SUBTITLE}</p>
          </div>

          {success ? (
            <div className="text-center space-y-3">
              <div className="surface-tone-celadon rounded-xl p-4 text-[13px] font-medium">
                注册成功，正在跳转到登录页…
              </div>
            </div>
          ) : (
            <div className="space-y-4" role="form" aria-label="注册表单">
              <div className="space-y-1.5">
                <Label htmlFor="username">用户名</Label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-foreground/25" />
                  <Input
                    id="username"
                    placeholder="至少 3 个字符"
                    className="pl-9"
                    value={username}
                    onChange={(event) => setUsername(event.target.value)}
                    onKeyDown={handleKeyDown}
                    autoComplete="username"
                    required
                    minLength={3}
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
                    placeholder="至少 6 个字符"
                    className="pl-9"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    onKeyDown={handleKeyDown}
                    autoComplete="new-password"
                    required
                    minLength={6}
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="confirmPassword">确认密码</Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-foreground/25" />
                  <Input
                    id="confirmPassword"
                    type="password"
                    placeholder="再次输入密码"
                    className="pl-9"
                    value={confirmPassword}
                    onChange={(event) => setConfirmPassword(event.target.value)}
                    onKeyDown={handleKeyDown}
                    autoComplete="new-password"
                    required
                    minLength={6}
                  />
                </div>
              </div>

              {error ? (
                <div
                  className="rounded-lg p-2.5 text-center text-[12px]"
                  style={{ color: SONG_COLORS.negative, backgroundColor: "rgba(182, 69, 60, 0.08)" }}
                >
                  {error}
                </div>
              ) : null}

              <Button
                type="submit"
                className="mt-2 w-full"
                disabled={loading}
                onClick={() => void handleRegister()}
              >
                {loading ? "注册中…" : "注册"}
              </Button>

              <div className="mt-4 text-center text-[12px] text-foreground/35">
                已有账户？{" "}
                <Link
                  href="/login"
                  className="font-medium text-foreground/60 transition-colors hover:text-foreground/80"
                >
                  返回登录
                </Link>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
