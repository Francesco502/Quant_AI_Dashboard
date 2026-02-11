"use client"

import { useState, useEffect, useCallback } from "react"
import { api as apiClient, SelectorConfig } from "@/lib/api"

/**
 * 统一策略 Hook — 所有需要策略列表的页面都从这里获取。
 * 数据来源：GET /stz/strategies（core/stocktradebyz/configs.json）
 *
 * 返回值:
 *  strategies  — 完整策略列表（SelectorConfig[]）
 *  active      — 仅激活的策略
 *  loading     — 是否正在加载
 *  refresh     — 手动刷新
 */
export function useStrategies() {
  const [strategies, setStrategies] = useState<SelectorConfig[]>([])
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const res = await apiClient.stz.listStrategies()
      if (res) setStrategies(res)
    } catch (e) {
      console.error("获取策略列表失败:", e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const active = strategies.filter(s => s.activate)

  return { strategies, active, loading, refresh }
}
