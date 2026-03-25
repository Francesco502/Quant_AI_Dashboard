"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Lock, User, UserPlus } from "lucide-react"
import { getEffectiveApiBaseUrl } from "@/lib/api"
import { SONG_COLORS } from "@/lib/chart-theme"
import { motion } from "framer-motion"
import Link from "next/link"

export default function RegisterPage() {
  const router = useRouter()
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [success, setSuccess] = useState(false)

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")

    if (username.length < 3) {
      setError("用户名至少3个字符")
      return
    }
    if (password.length < 6) {
      setError("密码至少6个字符")
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

      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.detail || "注册失败")
      }

      setSuccess(true)
      setTimeout(() => router.push("/login"), 2000)
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "注册失败，请稍后重试"
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex items-center justify-center min-h-[calc(100vh-200px)]">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        className="w-full max-w-sm"
      >
        <div className="glass-card rounded-2xl p-8">
          {/* Header */}
          <div className="text-center mb-8">
            <div className="w-10 h-10 rounded-xl bg-foreground/90 flex items-center justify-center mx-auto mb-4">
              <UserPlus className="h-4 w-4 text-background" />
            </div>
            <h1 className="text-lg font-semibold tracking-[-0.02em] text-foreground/90 mb-1">
              创建账户
            </h1>
            <p className="text-[13px] text-foreground/40">
              注册新的 Quant AI 研习台账户
            </p>
          </div>

          {success ? (
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="text-center space-y-3"
            >
              <div className="rounded-xl p-4 text-[13px] font-medium" style={{ color: SONG_COLORS.positive, backgroundColor: "rgba(77, 115, 88, 0.08)" }}>
                注册成功，正在跳转到登录页…
              </div>
            </motion.div>
          ) : (
            <form onSubmit={handleRegister} className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="username">用户名</Label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-foreground/25" />
                  <Input
                    id="username"
                    placeholder="至少3个字符"
                    className="pl-9"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    autoComplete="username"
                    required
                    minLength={3}
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="password">密码</Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-foreground/25" />
                  <Input
                    id="password"
                    type="password"
                    placeholder="至少6个字符"
                    className="pl-9"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete="new-password"
                    required
                    minLength={6}
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="confirmPassword">确认密码</Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-foreground/25" />
                  <Input
                    id="confirmPassword"
                    type="password"
                    placeholder="再次输入密码"
                    className="pl-9"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    autoComplete="new-password"
                    required
                    minLength={6}
                  />
                </div>
              </div>

              {error && (
                <motion.div
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="rounded-lg p-2.5 text-center text-[12px]"
                  style={{ color: SONG_COLORS.negative, backgroundColor: "rgba(182, 69, 60, 0.08)" }}
                >
                  {error}
                </motion.div>
              )}

              <Button type="submit" className="w-full mt-2" disabled={loading}>
                {loading ? "注册中..." : "注册"}
              </Button>

              <div className="text-center text-[12px] text-foreground/35 mt-4">
                已有账户？{" "}
                <Link href="/login" className="text-foreground/60 hover:text-foreground/80 font-medium transition-colors">
                  返回登录
                </Link>
              </div>
            </form>
          )}
        </div>
      </motion.div>
    </div>
  )
}
