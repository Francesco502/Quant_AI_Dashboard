"use client"
import { useState, useEffect, useCallback } from "react"
import { useSettings } from "@/lib/settings-context"
import { api } from "@/lib/api"
import { GlassCard, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Wallet, Server, ArrowUp, ArrowDown, X, Plus } from "lucide-react"
import { HelpTooltip } from "@/components/ui/tooltip"
import { GLOSSARY } from "@/lib/glossary"
import { formatCurrency } from "@/lib/utils"
import { API_BASE_URL } from "@/lib/api"

interface AccountData {
  total_assets: number;
  cash: number;
  market_value: number;
}

interface HealthStatus {
  api: boolean;
  apiLatency: number;
}

export default function SettingsPage() {
  const { dataSources, setDataSources, apiKeys, setApiKeys, isLoading } = useSettings()
  const [localKeys, setLocalKeys] = useState<Record<string, string>>({})
  const [accountData, setAccountData] = useState<AccountData | null>(null)
  const [accountLoading, setAccountLoading] = useState(true)
  const [healthStatus, setHealthStatus] = useState<HealthStatus>({ api: false, apiLatency: 0 })
  const [healthLoading, setHealthLoading] = useState(true)

  // 加载模拟账户数据
  const loadAccountData = useCallback(async () => {
    setAccountLoading(true)
    try {
      const res = await api.trading.paper.getAccount()
      if (res && res.status === "success" && res.portfolio) {
        setAccountData({
          total_assets: res.portfolio.total_assets,
          cash: res.portfolio.cash,
          market_value: res.portfolio.market_value,
        })
      }
    } catch {
      // 账户可能不存在
      setAccountData(null)
    } finally {
      setAccountLoading(false)
    }
  }, [])

  // 检查服务健康状态
  const checkHealth = useCallback(async () => {
    setHealthLoading(true)
    try {
      const start = performance.now()
      const res = await fetch(`${API_BASE_URL}/health`)
      const latency = Math.round(performance.now() - start)
      setHealthStatus({
        api: res.ok,
        apiLatency: latency,
      })
    } catch {
      setHealthStatus({ api: false, apiLatency: 0 })
    } finally {
      setHealthLoading(false)
    }
  }, [])

  useEffect(() => {
    if (Object.keys(apiKeys).length > 0) {
        setLocalKeys(prev => ({ ...prev, ...apiKeys }))
    }
  }, [apiKeys])

  useEffect(() => {
    loadAccountData()
    checkHealth()
  }, [loadAccountData, checkHealth])

  const addSource = (source: string) => {
    if (!dataSources.includes(source)) {
      setDataSources([...dataSources, source])
    }
  }

  const removeSource = (source: string) => {
    setDataSources(dataSources.filter(s => s !== source))
  }

  const moveSource = (index: number, direction: number) => {
    const newSources = [...dataSources]
    const targetIndex = index + direction
    if (targetIndex >= 0 && targetIndex < newSources.length) {
      [newSources[index], newSources[targetIndex]] = [newSources[targetIndex], newSources[index]]
      setDataSources(newSources)
    }
  }

  if (isLoading) {
      return <div className="p-10 flex justify-center text-muted-foreground">Loading settings...</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-[-0.02em] text-foreground/90">系统设置</h1>
        <p className="text-muted-foreground">
          管理数据源、模拟账户和服务状态。
        </p>
      </div>

      <Tabs defaultValue="account" className="space-y-6">
        <TabsList>
          <TabsTrigger value="account" className="gap-2">
            <Wallet className="h-4 w-4" /> 模拟账户 (Paper Account)
          </TabsTrigger>
          <TabsTrigger value="daemon" className="gap-2">
            <Server className="h-4 w-4" /> 服务状态 (Daemon)
          </TabsTrigger>
          <TabsTrigger value="data" className="gap-2">
            <Server className="h-4 w-4" /> 数据源 (Data Sources)
          </TabsTrigger>
        </TabsList>

        <TabsContent value="account">
          <GlassCard>
            <CardTitle className="flex items-center">
               {GLOSSARY.PaperAccount.term}
               <HelpTooltip content={GLOSSARY.PaperAccount.definition} />
            </CardTitle>
            <CardDescription>使用虚拟资金模拟真实交易。</CardDescription>
            
            {accountLoading ? (
              <div className="mt-8 text-center text-muted-foreground">加载中...</div>
            ) : accountData ? (
              <>
                <div className="mt-8 grid gap-6 md:grid-cols-3">
                  <div className="p-5 bg-black/[0.02] dark:bg-white/[0.04] rounded-xl">
                    <div className="text-sm text-muted-foreground mb-1">总资产 (Total Assets)</div>
                    <div className="text-2xl font-bold">{formatCurrency(accountData.total_assets)}</div>
                  </div>
                  <div className="p-5 bg-black/[0.02] dark:bg-white/[0.04] rounded-xl">
                    <div className="text-sm text-muted-foreground mb-1">持仓市值 (Market Value)</div>
                    <div className="text-2xl font-bold text-blue-500">{formatCurrency(accountData.market_value)}</div>
                  </div>
                  <div className="p-5 bg-black/[0.02] dark:bg-white/[0.04] rounded-xl">
                    <div className="text-sm text-muted-foreground mb-1">可用现金 (Available Cash)</div>
                    <div className="text-2xl font-bold">{formatCurrency(accountData.cash)}</div>
                  </div>
                </div>
                <div className="mt-8 flex justify-end gap-4">
                  <Button variant="outline" onClick={loadAccountData}>刷新 (Refresh)</Button>
                </div>
              </>
            ) : (
              <div className="mt-8 text-center text-muted-foreground">
                <p>暂无模拟账户，请在交易页面创建。</p>
              </div>
            )}
          </GlassCard>
        </TabsContent>

        <TabsContent value="daemon">
          <GlassCard>
            <CardTitle className="mb-6 flex items-center justify-between">
              <span>系统健康 (System Health)</span>
              <Button variant="outline" size="sm" onClick={checkHealth} disabled={healthLoading}>
                {healthLoading ? "检测中..." : "刷新状态"}
              </Button>
            </CardTitle>
            <div className="space-y-4">
              {/* API Server Status - from real health check */}
              <div className={`flex items-center justify-between p-4 rounded-xl border ${
                healthStatus.api 
                  ? "bg-emerald-500/10 border-emerald-500/20" 
                  : "bg-red-500/10 border-red-500/20"
              }`}>
                <div className="flex items-center gap-3">
                  <div className={`h-2.5 w-2.5 rounded-full ${
                    healthStatus.api ? "bg-emerald-500 animate-pulse" : "bg-red-500"
                  }`} />
                  <span className="font-medium">API 服务 (API Server)</span>
                </div>
                <span className={`text-sm font-mono ${
                  healthStatus.api ? "text-emerald-600" : "text-red-500"
                }`}>
                  {healthLoading ? "检测中..." : healthStatus.api ? `运行中 (${healthStatus.apiLatency}ms)` : "离线 (Offline)"}
                </span>
              </div>
              
              {/* Data Feeder - depends on API being online */}
              <div className={`flex items-center justify-between p-4 rounded-xl border ${
                healthStatus.api 
                  ? "bg-emerald-500/10 border-emerald-500/20" 
                  : "bg-gray-100 dark:bg-gray-800 border-border"
              }`}>
                <div className="flex items-center gap-3">
                  <div className={`h-2.5 w-2.5 rounded-full ${
                    healthStatus.api ? "bg-emerald-500 animate-pulse" : "bg-gray-400"
                  }`} />
                  <span className={`font-medium ${!healthStatus.api ? "text-muted-foreground" : ""}`}>
                    数据馈送 (Data Feeder)
                  </span>
                </div>
                <span className={`text-sm font-mono ${
                  healthStatus.api ? "text-emerald-600" : "text-muted-foreground"
                }`}>
                  {healthStatus.api ? "已连接 (Connected)" : "未连接"}
                </span>
              </div>

              <div className="flex items-center justify-between p-4 bg-gray-100 dark:bg-gray-800 rounded-xl">
                <div className="flex items-center gap-3">
                  <div className="h-2.5 w-2.5 rounded-full bg-gray-400" />
                  <span className="font-medium text-muted-foreground">信号引擎 (Signal Engine)</span>
                </div>
                <span className="text-sm text-muted-foreground font-mono">空闲 (Idle)</span>
              </div>
            </div>
          </GlassCard>
        </TabsContent>

        <TabsContent value="data">
            <GlassCard>
              <CardTitle className="mb-4 flex items-center">
                {GLOSSARY.DataSources.term}
                <HelpTooltip content={GLOSSARY.DataSources.definition} />
              </CardTitle>
              <CardDescription className="mb-6">
                配置并排序数据源优先级。系统将按顺序尝试获取数据。
              </CardDescription>

              <div className="space-y-6">
                {/* Active Sources */}
                <div className="space-y-3">
                  <h3 className="text-sm font-medium text-muted-foreground">已启用 (Active & Sorted)</h3>
                  {dataSources.map((source, index) => (
                    <div key={source} className="flex items-center justify-between p-3 bg-secondary/50 rounded-xl border border-border">
                      <span className="font-medium flex items-center gap-2">
                        <span className="flex items-center justify-center w-5 h-5 rounded-full bg-primary/10 text-primary text-xs">
                          {index + 1}
                        </span>
                        {source}
                      </span>
                      <div className="flex items-center gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={() => moveSource(index, -1)}
                          disabled={index === 0}
                        >
                          <ArrowUp className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={() => moveSource(index, 1)}
                          disabled={index === dataSources.length - 1}
                        >
                          <ArrowDown className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-destructive hover:text-destructive"
                          onClick={() => removeSource(source)}
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  ))}
                  {dataSources.length === 0 && (
                      <div className="text-sm text-muted-foreground p-4 text-center border border-dashed rounded-xl">
                          暂无已启用数据源，请从下方添加。
                      </div>
                  )}
                </div>

                {/* Available Sources */}
                <div className="space-y-3">
                  <h3 className="text-sm font-medium text-muted-foreground">可添加 (Available)</h3>
                  <div className="grid gap-2 grid-cols-2 sm:grid-cols-3">
                    {["AkShare", "Binance", "AlphaVantage", "Tushare", "yfinance"]
                      .filter(s => !dataSources.includes(s))
                      .map(source => (
                      <Button
                        key={source}
                        variant="outline"
                        className="justify-start gap-2"
                        onClick={() => addSource(source)}
                      >
                        <Plus className="h-4 w-4" />
                        {source}
                      </Button>
                    ))}
                  </div>
                </div>

                {/* API Configuration */}
                <div className="space-y-3 pt-4 border-t border-border/50">
                  <h3 className="text-sm font-medium text-muted-foreground">API 配置 (API Configuration)</h3>
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Tushare Token</label>
                      <Input 
                        value={localKeys["Tushare"] || ""} 
                        onChange={(e) => setLocalKeys({ ...localKeys, "Tushare": e.target.value })}
                        onBlur={() => setApiKeys(localKeys)}
                        placeholder="输入 Tushare Token"
                        type="password"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Alpha Vantage Key</label>
                      <Input 
                        value={localKeys["AlphaVantage"] || ""} 
                        onChange={(e) => setLocalKeys({ ...localKeys, "AlphaVantage": e.target.value })}
                        onBlur={() => setApiKeys(localKeys)}
                        placeholder="输入 Alpha Vantage API Key"
                        type="password"
                      />
                    </div>
                  </div>
                </div>
              </div>
            </GlassCard>
        </TabsContent>
      </Tabs>
    </div>
  )
}
