"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { useAuth } from "@/lib/auth-context"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Lock, User } from "lucide-react"
import { API_BASE_URL } from "@/lib/api"
import { motion } from "framer-motion"
import Link from "next/link"

export default function LoginPage() {
  const router = useRouter()
  const { login } = useAuth()
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError("")

    try {
      const formData = new URLSearchParams()
      formData.append('username', username)
      formData.append('password', password)

      const res = await fetch(`${API_BASE_URL}/auth/token`, {
          method: "POST",
          headers: {
              'Content-Type': 'application/x-www-form-urlencoded',
          },
          body: formData
      })

      if (!res.ok) {
        if (res.status === 401) {
          setError("用户名或密码错误")
          return
        }
        if (res.status >= 500 || res.status === 0) {
          setError("服务暂时不可用，请稍后重试")
          return
        }
        const msg = (await res.json().catch(() => ({}))).detail || "登录失败"
        setError(typeof msg === "string" ? msg : "登录失败")
        return
      }

      const data = await res.json()
      login(data.access_token, username)
      
    } catch (err) {
      const msg = (err as Error)?.message ?? ""
      const isNetwork = typeof msg === "string" && /fetch|network|loaded|connection/i.test(msg)
      setError(isNetwork
        ? "无法连接服务器，请确认 API 已启动（默认端口 8685）"
        : "用户名或密码错误")
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
              <span className="text-background text-sm font-bold">Q</span>
            </div>
            <h1 className="text-lg font-semibold tracking-[-0.02em] text-foreground/90 mb-1">
              登录
            </h1>
            <p className="text-[13px] text-foreground/40">
              登录到 Quant AI Dashboard
            </p>
          </div>

          <form onSubmit={handleLogin} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="username">用户名</Label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-foreground/25" />
                <Input 
                  id="username"
                  placeholder="admin" 
                  className="pl-9"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
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
                  placeholder="••••••" 
                  className="pl-9"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </div>
            </div>

            {error && (
              <motion.div
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                className="text-[12px] text-red-500/80 text-center bg-red-500/[0.06] p-2.5 rounded-lg"
              >
                {error}
              </motion.div>
            )}

            <Button type="submit" className="w-full mt-2" disabled={loading}>
              {loading ? "登录中..." : "登录"}
            </Button>
            
            <div className="text-center text-[12px] text-foreground/35 mt-4 space-y-2">
              <div>
                还没有账户?{" "}
                <Link href="/register" className="text-foreground/60 hover:text-foreground/80 font-medium transition-colors">
                  注册新账户
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
