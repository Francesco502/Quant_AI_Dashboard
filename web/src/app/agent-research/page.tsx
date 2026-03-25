"use client"

import { useEffect, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { GlassCard } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { api, type AgentResearchResponse } from "@/lib/api"

type LlmConfigState = {
  configured: boolean
  provider: string | null
  model: string | null
  message?: string
}

export default function AgentResearchPage() {
  const [config, setConfig] = useState<LlmConfigState | null>(null)
  const [query, setQuery] = useState("比较 600519 和 000858 的价格趋势、市场环境与估值差异")
  const [model, setModel] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [result, setResult] = useState<AgentResearchResponse | null>(null)

  useEffect(() => {
    void api.llmAnalysis.getConfig().then(setConfig).catch((requestError) => {
      setError(requestError instanceof Error ? requestError.message : "读取配置失败")
    })
  }, [])

  const handleRun = async () => {
    if (!config?.configured) return
    setLoading(true)
    setError("")
    setResult(null)
    try {
      const response = await api.agent.research({
        query,
        model: model.trim() || null,
      })
      setResult(response)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Agent 研究失败")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-[-0.02em] text-foreground/90">Agent 研究</h1>
        <p className="text-sm text-muted-foreground">独立页面，直接调用后端 Agent 研究接口，而不是再跳转到别处。</p>
      </div>

      <GlassCard className="space-y-4 p-5">
        <div className="flex flex-wrap items-center gap-3">
          <Badge variant={config?.configured ? "default" : "secondary"}>
            {config?.configured ? "已配置" : "未配置"}
          </Badge>
          <span className="text-sm text-muted-foreground">
            Provider: {config?.provider || "-"} / Model: {config?.model || "-"}
          </span>
        </div>

        {config?.message ? <p className="text-sm text-amber-600">{config.message}</p> : null}

        <div className="space-y-2">
          <Label>研究问题</Label>
          <textarea
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="min-h-40 w-full rounded-md border bg-background px-3 py-2 text-sm"
            placeholder="输入你的研究问题"
          />
        </div>

        <div className="space-y-2">
          <Label>模型覆盖</Label>
          <Input value={model} onChange={(event) => setModel(event.target.value)} placeholder="留空使用服务端默认模型" />
        </div>

        <Button onClick={() => void handleRun()} disabled={loading || !config?.configured}>
          {loading ? "研究中..." : "开始研究"}
        </Button>
      </GlassCard>

      {error ? <div className="rounded-lg bg-red-500/10 p-4 text-sm text-red-600">{error}</div> : null}

      {result ? (
        <GlassCard className="space-y-4 p-5">
          <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
            <span>迭代次数 {result.iterations}</span>
            <span>工具调用 {result.tools_used.length}</span>
            {result.scratchpad_path ? <span>Scratchpad 已生成</span> : null}
          </div>

          <div className="rounded-lg bg-muted/30 p-4 text-sm whitespace-pre-wrap">{result.answer}</div>

          {result.tool_results.length ? (
            <div className="space-y-3">
              <h2 className="text-lg font-semibold">工具结果</h2>
              {result.tool_results.map((tool) => (
                <div key={`${tool.name}-${JSON.stringify(tool.args)}`} className="rounded-lg border p-4">
                  <div className="mb-2 font-medium">{tool.name}</div>
                  <pre className="overflow-x-auto text-xs text-muted-foreground">
                    {JSON.stringify(tool.data, null, 2)}
                  </pre>
                </div>
              ))}
            </div>
          ) : null}
        </GlassCard>
      ) : null}
    </div>
  )
}
