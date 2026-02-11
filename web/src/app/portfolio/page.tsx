"use client"

import { useState, useEffect } from "react"
import { api as apiClient, Asset } from "@/lib/api"
import { GlassCard } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { PieChart, Plus, Trash2, RefreshCcw, AlertCircle, CheckCircle, Edit2, Check, X } from "lucide-react"
import { HelpTooltip } from "@/components/ui/tooltip"

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

export default function PortfolioPage() {
  const [tickers, setTickers] = useState<Asset[]>([])
  const [loading, setLoading] = useState(true)
  const [newTicker, setNewTicker] = useState("")
  const [newTickerType, setNewTickerType] = useState("A_STOCK") // "A_STOCK" | "HK_STOCK" | "US_STOCK" | "OTC_FUND"
  const [adding, setAdding] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)
  
  // 编辑别名状态
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editAlias, setEditAlias] = useState("")

  const fetchAssetPool = async () => {
    setLoading(true)
    try {
      const res = await apiClient.stz.getAssetPool()
      if (res) {
        setTickers(res)
      }
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const formatTicker = (input: string, type: string): string => {
    let ticker = input.trim().toUpperCase()
    
    // 如果已经包含后缀，优先使用用户输入的后缀
    if (ticker.includes('.')) {
        return ticker
    }

    if (type === "OTC_FUND") {
        return ticker + ".OF"
    } else if (type === "HK_STOCK") {
        return ticker + ".HK"
    } else if (type === "US_STOCK") {
        return ticker // 美股通常不需要后缀，或者由后端处理
    } else {
        // A_STOCK: 尝试自动推断
        if (/^\d{6}$/.test(ticker)) {
           if (ticker.startsWith('6') || ticker.startsWith('5')) {
             return ticker + '.SS'
           } else if (ticker.startsWith('0') || ticker.startsWith('3') || ticker.startsWith('15') || ticker.startsWith('16')) {
             return ticker + '.SZ'
           }
        }
    }
    return ticker
  }

  const handleAddTicker = async () => {
    if (!newTicker.trim()) return
    setAdding(true)
    setMessage(null)
    try {
      const formatted = formatTicker(newTicker, newTickerType)
      const res = await apiClient.stz.addAsset(formatted)
      if (res.status === 'success') {
          setTickers(res.pool)
          setNewTicker("")
          setMessage({ type: 'success', text: res.message })
      } else {
          setMessage({ type: 'error', text: res.message || "添加失败" })
      }
    } catch (e) {
      console.error(e)
      setMessage({ type: 'error', text: "添加失败: " + String(e) })
    } finally {
      setAdding(false)
      setTimeout(() => setMessage(null), 3000)
    }
  }

  const handleRemoveTicker = async (tickerToRemove: string) => {
    if (!confirm(`确定要从资产池中移除 ${tickerToRemove} 吗？`)) return
    try {
      const res = await apiClient.stz.deleteAsset(tickerToRemove)
      if (res.status === 'success') {
          setTickers(res.pool)
          setMessage({ type: 'success', text: res.message })
      } else {
          setMessage({ type: 'error', text: res.message || "删除失败" })
      }
    } catch (e) {
      console.error(e)
      setMessage({ type: 'error', text: "删除失败: " + String(e) })
    } finally {
      setTimeout(() => setMessage(null), 3000)
    }
  }

  const startEditing = (asset: Asset) => {
      setEditingId(asset.ticker)
      setEditAlias(asset.alias || "")
  }

  const cancelEditing = () => {
      setEditingId(null)
      setEditAlias("")
  }

  const saveAlias = async (ticker: string) => {
      try {
          const res = await apiClient.stz.updateAssetAlias(ticker, editAlias)
          if (res.status === 'success') {
              setTickers(res.pool)
              setMessage({ type: 'success', text: "别名已更新" })
          }
      } catch (e) {
          console.error(e)
          setMessage({ type: 'error', text: "更新别名失败" })
      } finally {
          setEditingId(null)
          setTimeout(() => setMessage(null), 3000)
      }
  }

  useEffect(() => {
    fetchAssetPool()
  }, [])

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-[-0.02em] text-foreground/90 flex items-center gap-2">
            资产池管理
            <HelpTooltip content="您关注的股票或基金集合，用于后续的策略选股与回测。" />
          </h1>
          <p className="text-muted-foreground">
            管理您的核心关注资产列表，这些资产将作为“资产池评估”模式的基础输入。
          </p>
        </div>
        <Button variant="outline" size="icon" onClick={fetchAssetPool} disabled={loading}>
          <RefreshCcw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
        </Button>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        <GlassCard className="md:col-span-2">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-6 gap-4">
            <h2 className="text-xl font-semibold flex items-center gap-2">
              资产列表
              <Badge variant="secondary">{tickers.length}</Badge>
            </h2>
            <div className="flex flex-wrap gap-2">
              <Select value={newTickerType} onValueChange={setNewTickerType}>
                <SelectTrigger className="w-[120px]">
                  <SelectValue placeholder="资产类型" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="A_STOCK">A股/ETF</SelectItem>
                  <SelectItem value="OTC_FUND">场外基金</SelectItem>
                  <SelectItem value="HK_STOCK">港股</SelectItem>
                  <SelectItem value="US_STOCK">美股</SelectItem>
                </SelectContent>
              </Select>
              <Input 
                placeholder="输入代码 (如 600519)" 
                value={newTicker}
                onChange={(e) => setNewTicker(e.target.value)}
                className="w-48"
                onKeyDown={(e) => e.key === 'Enter' && handleAddTicker()}
              />
              <Button onClick={handleAddTicker} disabled={adding || !newTicker}>
                {adding ? <RefreshCcw className="h-4 w-4 animate-spin mr-1" /> : <Plus className="h-4 w-4 mr-1" />} 添加
              </Button>
            </div>
          </div>
          
          {message && (
            <div className={`mb-4 p-3 rounded-lg flex items-center gap-2 text-sm ${
              message.type === 'success' ? 'bg-emerald-50 text-emerald-600 border border-emerald-100' : 'bg-red-50 text-red-600 border border-red-100'
            }`}>
              {message.type === 'success' ? <CheckCircle className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
              {message.text}
            </div>
          )}

          <div className="rounded-md border overflow-x-auto">
            <Table className="min-w-[600px]">
              <TableHeader>
                <TableRow>
                  <TableHead>代码</TableHead>
                  <TableHead>官方名称</TableHead>
                  <TableHead>自定义名称</TableHead>
                  <TableHead className="text-right">最新价格</TableHead>
                  <TableHead className="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tickers.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={4} className="text-center h-24 text-muted-foreground">
                      资产池为空，请添加资产
                    </TableCell>
                  </TableRow>
                ) : (
                  tickers.map((asset) => (
                    <TableRow key={asset.ticker}>
                      <TableCell className="font-medium">{asset.ticker}</TableCell>
                      <TableCell className="text-muted-foreground">
                          {asset.name || "-"}
                      </TableCell>
                      <TableCell>
                          {editingId === asset.ticker ? (
                              <div className="flex items-center gap-1">
                                  <Input 
                                      value={editAlias} 
                                      onChange={(e) => setEditAlias(e.target.value)}
                                      className="h-7 w-32"
                                      autoFocus
                                      onKeyDown={(e) => {
                                          if (e.key === 'Enter') saveAlias(asset.ticker);
                                          if (e.key === 'Escape') cancelEditing();
                                      }}
                                  />
                                  <Button size="icon" variant="ghost" className="h-7 w-7 text-emerald-500" onClick={() => saveAlias(asset.ticker)}>
                                      <Check className="h-4 w-4" />
                                  </Button>
                                  <Button size="icon" variant="ghost" className="h-7 w-7 text-muted-foreground" onClick={cancelEditing}>
                                      <X className="h-4 w-4" />
                                  </Button>
                              </div>
                          ) : (
                              <div className="flex items-center gap-2 group">
                                  <span>{asset.alias || "-"}</span>
                                  <Button 
                                      size="icon" 
                                      variant="ghost" 
                                      className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
                                      onClick={() => startEditing(asset)}
                                  >
                                      <Edit2 className="h-3 w-3 text-muted-foreground" />
                                  </Button>
                              </div>
                          )}
                      </TableCell>
                      <TableCell className="text-right font-mono">
                          {asset.last_price ? `¥${asset.last_price.toFixed(3)}` : '-'}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button variant="ghost" size="icon" className="h-8 w-8 text-red-500 hover:text-red-600 hover:bg-red-50" onClick={() => handleRemoveTicker(asset.ticker)}>
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </GlassCard>

        <GlassCard className="h-fit">
          <h3 className="font-semibold mb-4 flex items-center gap-2">
            关于资产池
            <PieChart className="h-4 w-4 text-blue-500" />
          </h3>
          <div className="space-y-4 text-sm text-muted-foreground">
            <p>
              <span className="font-medium text-foreground">什么是资产池？</span>
              <br />
              资产池是您自定义的一组关注标的。在运行战法选股时，您可以选择仅对资产池内的标的进行扫描，这样可以聚焦于您熟悉的股票，提高交易效率。
            </p>
            <div>
              <span className="font-medium text-foreground">如何添加？</span>
              <br />
              输入标准的证券代码并点击添加。
              <ul className="list-disc pl-4 mt-1 space-y-1">
                <li>股票/ETF：直接输入代码（如 600519, 159915）会自动补全后缀。</li>
                <li>场外基金：请手动添加 <b>.OF</b> 后缀（如 002611.OF）以避免与股票代码冲突。</li>
              </ul>
            </div>
            <p>
              <span className="font-medium text-foreground">数据同步</span>
              <br />
              此处的修改会自动保存到您的配置文件中，并在所有设备上同步（如果使用了云端部署）。
            </p>
          </div>
        </GlassCard>
      </div>
    </div>
  )
}
