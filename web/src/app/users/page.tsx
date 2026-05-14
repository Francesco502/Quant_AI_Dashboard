"use client"

import { useCallback, useDeferredValue, useEffect, useMemo, useState } from "react"
import { motion } from "framer-motion"
import { AlertCircle, RefreshCw, Shield, Trash2, Users } from "lucide-react"

import { Button } from "@/components/ui/button"
import { GlassCard, CardDescription, CardTitle } from "@/components/ui/card"
import { CardSkeleton, TableSkeleton } from "@/components/ui/skeleton"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { fetchApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { formatDateTimeInBeijing } from "@/lib/time"

type UserRow = {
  id: number
  username: string
  role: string
  assigned_at: string
  assigned_by: string | null
}

type UserListResponse = {
  status: string
  count: number
  users: UserRow[]
}

type UpdateRoleResponse = {
  status: string
  message: string
  username: string
  new_role: string
}

const validRoles = ["admin", "trader", "analyst", "viewer"] as const
const USERS_PAGE_SIZE = 20
const roleLabels: Record<(typeof validRoles)[number], string> = {
  admin: "管理员",
  trader: "交易员",
  analyst: "研究员",
  viewer: "只读",
}

export default function UsersPage() {
  const { user: currentUser } = useAuth()
  const [users, setUsers] = useState<UserRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [message, setMessage] = useState("")
  const [selectedUser, setSelectedUser] = useState<UserRow | null>(null)
  const [nextRole, setNextRole] = useState<string>("viewer")
  const [editOpen, setEditOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [userQuery, setUserQuery] = useState("")
  const [roleFilter, setRoleFilter] = useState<"all" | (typeof validRoles)[number]>("all")
  const [page, setPage] = useState(1)
  const deferredUserQuery = useDeferredValue(userQuery)

  const isAdmin = currentUser?.role === "admin"

  const clearNotice = useCallback(() => {
    window.setTimeout(() => {
      setError("")
      setMessage("")
    }, 3000)
  }, [])

  const loadUsers = useCallback(async () => {
    if (!isAdmin) {
      setLoading(false)
      return
    }

    setLoading(true)
    setError("")
    try {
      const response = await fetchApi<UserListResponse>("/auth/users")
      setUsers(response.users || [])
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "加载用户列表失败")
    } finally {
      setLoading(false)
    }
  }, [isAdmin])

  useEffect(() => {
    void loadUsers()
  }, [loadUsers])

  const sortedUsers = useMemo(
    () => [...users].sort((left, right) => left.username.localeCompare(right.username, "zh-CN")),
    [users]
  )
  const filteredUsers = useMemo(() => {
    const normalizedQuery = deferredUserQuery.trim().toLowerCase()
    return sortedUsers.filter((user) => {
      const matchesRole = roleFilter === "all" || user.role === roleFilter
      if (!matchesRole) return false
      if (!normalizedQuery) return true

      return [user.username, user.role, user.assigned_by || ""]
        .join(" ")
        .toLowerCase()
        .includes(normalizedQuery)
    })
  }, [deferredUserQuery, roleFilter, sortedUsers])
  const totalPages = Math.max(1, Math.ceil(filteredUsers.length / USERS_PAGE_SIZE))
  const currentPage = Math.min(page, totalPages)
  const visibleUsers = useMemo(
    () => filteredUsers.slice((currentPage - 1) * USERS_PAGE_SIZE, currentPage * USERS_PAGE_SIZE),
    [currentPage, filteredUsers],
  )
  const resultRangeStart = filteredUsers.length === 0 ? 0 : (currentPage - 1) * USERS_PAGE_SIZE + 1
  const resultRangeEnd = Math.min(currentPage * USERS_PAGE_SIZE, filteredUsers.length)

  const handleUpdateRole = async () => {
    if (!selectedUser) return

    try {
      const response = await fetchApi<UpdateRoleResponse>(`/auth/users/${selectedUser.username}/role`, {
        method: "PUT",
        body: JSON.stringify({ role: nextRole }),
      })
      setMessage(response.message || `已更新 ${selectedUser.username} 的角色`)
      setEditOpen(false)
      setSelectedUser(null)
      await loadUsers()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "更新角色失败")
    } finally {
      clearNotice()
    }
  }

  const handleDeleteUser = async () => {
    if (!selectedUser) return

    try {
      const response = await fetchApi<{ message?: string }>(`/auth/users/${selectedUser.username}`, {
        method: "DELETE",
      })
      setMessage(response.message || `已删除用户 ${selectedUser.username}`)
      setDeleteOpen(false)
      setSelectedUser(null)
      await loadUsers()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "删除用户失败")
    } finally {
      clearNotice()
    }
  }

  const openRoleDialog = (user: UserRow) => {
    setSelectedUser(user)
    setNextRole(user.role)
    setEditOpen(true)
  }

  const openDeleteDialog = (user: UserRow) => {
    setSelectedUser(user)
    setDeleteOpen(true)
  }

  if (!isAdmin) {
    return (
      <div className="flex min-h-[calc(100vh-220px)] items-center justify-center">
        <GlassCard className="max-w-md p-8 text-center">
          <AlertCircle className="mx-auto mb-4 h-12 w-12 text-muted-foreground" />
          <h1 className="section-title mb-2">无权访问</h1>
          <p className="text-sm text-muted-foreground">只有管理员可以查看和管理系统用户。</p>
        </GlassCard>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="page-title">用户管理</h1>
          <p className="page-subtitle">查看用户、调整角色并清理无效账号。</p>
        </div>
        <Button onClick={() => void loadUsers()} variant="outline" disabled={loading}>
          <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          刷新
        </Button>
      </div>

      {error ? (
        <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} className="surface-tone-cinnabar rounded-lg border p-4 text-sm text-tone-cinnabar">
          {error}
        </motion.div>
      ) : null}

      {message ? (
        <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} className="surface-tone-celadon rounded-lg border p-4 text-sm text-tone-celadon">
          {message}
        </motion.div>
      ) : null}

      <GlassCard className="p-6">
        <CardTitle className="flex items-center gap-2">
          <Users className="h-5 w-5" />
          用户列表
        </CardTitle>
        <CardDescription>当前共 {sortedUsers.length} 个用户，已筛选 {filteredUsers.length} 个</CardDescription>

        <div className="mt-5 grid gap-3 lg:grid-cols-[1fr_220px_auto] lg:items-end">
          <div className="space-y-2">
            <Label htmlFor="user-search">搜索用户</Label>
            <Input
              id="user-search"
              value={userQuery}
              onChange={(event) => {
                setUserQuery(event.target.value)
                setPage(1)
              }}
              placeholder="输入用户名、角色或分配人"
            />
          </div>
          <div className="space-y-2">
            <Label>角色筛选</Label>
            <Select
              value={roleFilter}
              onValueChange={(value) => {
                setRoleFilter(value as typeof roleFilter)
                setPage(1)
              }}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部角色</SelectItem>
                {validRoles.map((role) => (
                  <SelectItem key={role} value={role}>
                    {roleLabels[role]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="rounded-2xl border border-border/60 bg-muted/20 px-4 py-3 text-sm leading-6 text-muted-foreground">
            {resultRangeStart}-{resultRangeEnd} / {filteredUsers.length}
          </div>
        </div>

        <div className="mt-6 space-y-3 lg:hidden">
          {loading ? (
            <CardSkeleton rows={5} />
          ) : filteredUsers.length === 0 ? (
            <div className="data-panel-muted rounded-[24px] px-5 py-8 text-center text-sm text-muted-foreground">
              暂无匹配用户
            </div>
          ) : (
            visibleUsers.map((user) => (
              <div key={`${user.id}-mobile`} className="rounded-[24px] border border-border/60 bg-background/72 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-base font-medium text-foreground">{user.username}</div>
                    <div className="mt-2 inline-flex items-center gap-1 rounded-full bg-foreground/5 px-2.5 py-1 text-xs font-medium capitalize">
                      <Shield className="h-3.5 w-3.5" />
                      {roleLabels[user.role as keyof typeof roleLabels] || user.role}
                    </div>
                  </div>
                  <div className="text-right text-xs leading-6 text-muted-foreground">
                    <div>{user.assigned_at ? formatDateTimeInBeijing(user.assigned_at, {}, user.assigned_at) : "-"}</div>
                    <div>{user.assigned_by || "系统"}</div>
                  </div>
                </div>
                <div className="mt-4 grid grid-cols-2 gap-2">
                  <Button variant="outline" size="sm" onClick={() => openRoleDialog(user)}>
                    修改角色
                  </Button>
                  {user.username !== currentUser?.username && user.username !== "admin" ? (
                    <Button variant="destructive" size="sm" onClick={() => openDeleteDialog(user)}>
                      <Trash2 className="mr-1 h-4 w-4" />
                      删除
                    </Button>
                  ) : (
                    <Button variant="ghost" size="sm" disabled>
                      当前账号
                    </Button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>

        <div className="mt-6 hidden overflow-x-auto lg:block">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>用户名</TableHead>
                <TableHead>角色</TableHead>
                <TableHead>分配时间</TableHead>
                <TableHead>分配人</TableHead>
                <TableHead className="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={5} className="p-4">
                    <TableSkeleton rows={5} cols={5} />
                  </TableCell>
                </TableRow>
              ) : filteredUsers.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="py-10 text-center text-muted-foreground">
                    暂无匹配用户
                  </TableCell>
                </TableRow>
              ) : (
                visibleUsers.map((user) => (
                  <TableRow key={user.id}>
                    <TableCell className="font-medium">{user.username}</TableCell>
                    <TableCell>
                      <span className="inline-flex items-center gap-1 rounded-full bg-foreground/5 px-2.5 py-1 text-xs font-medium capitalize">
                        <Shield className="h-3.5 w-3.5" />
                        {roleLabels[user.role as keyof typeof roleLabels] || user.role}
                      </span>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {user.assigned_at ? formatDateTimeInBeijing(user.assigned_at, {}, user.assigned_at) : "-"}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{user.assigned_by || "系统"}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button variant="outline" size="sm" onClick={() => openRoleDialog(user)}>
                          修改角色
                        </Button>
                        {user.username !== currentUser?.username && user.username !== "admin" ? (
                          <Button variant="destructive" size="sm" onClick={() => openDeleteDialog(user)}>
                            <Trash2 className="mr-1 h-4 w-4" />
                            删除
                          </Button>
                        ) : null}
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>

        {filteredUsers.length > USERS_PAGE_SIZE ? (
          <div className="mt-5 flex flex-col gap-3 border-t border-border/60 pt-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-sm text-muted-foreground">
              第 {currentPage} / {totalPages} 页，每页 {USERS_PAGE_SIZE} 个用户
            </div>
            <div className="grid grid-cols-2 gap-2 sm:flex">
              <Button
                variant="outline"
                size="sm"
                disabled={currentPage <= 1}
                onClick={() => setPage((value) => Math.max(1, value - 1))}
              >
                上一页
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={currentPage >= totalPages}
                onClick={() => setPage((value) => Math.min(totalPages, value + 1))}
              >
                下一页
              </Button>
            </div>
          </div>
        ) : null}
      </GlassCard>

      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>修改用户角色</DialogTitle>
            <DialogDescription>角色变更会立即影响该账号的访问权限。</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label>用户名</Label>
              <Input value={selectedUser?.username || ""} disabled />
            </div>
            <div className="space-y-2">
              <Label>新角色</Label>
              <Select value={nextRole} onValueChange={setNextRole}>
                <SelectTrigger>
                  <SelectValue placeholder="选择角色" />
                </SelectTrigger>
                <SelectContent>
                  {validRoles.map((role) => (
                    <SelectItem key={role} value={role}>
                      {roleLabels[role]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditOpen(false)}>
              取消
            </Button>
            <Button onClick={() => void handleUpdateRole()} disabled={!selectedUser || nextRole === selectedUser.role}>
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>删除用户</DialogTitle>
            <DialogDescription>
              该操作会删除用户账号及其关联的纸面交易数据，且无法撤销。
            </DialogDescription>
          </DialogHeader>
          <div className="py-2 text-sm text-foreground/80">
            确认删除用户 <strong>{selectedUser?.username}</strong>？
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteOpen(false)}>
              取消
            </Button>
            <Button variant="destructive" onClick={() => void handleDeleteUser()}>
              确认删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
