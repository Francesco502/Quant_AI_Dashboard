"use client"

import { Area, AreaChart, CartesianGrid, Tooltip, XAxis, YAxis } from "recharts"

import { MeasuredChart } from "@/components/charts/measured-chart"
import { EmptyState } from "@/components/data/empty-state"
import { MetricCard } from "@/components/data/metric-card"
import { PanelHeader } from "@/components/data/panel-header"
import { GlassCard } from "@/components/ui/card"
interface ChartEquityPoint {
  date: string
  equity: number
}
import { SONG_COLORS } from "@/lib/chart-theme"
import { formatCurrency } from "@/lib/utils"

export function SummaryMetric({
  label,
  value,
  tone = "default",
  accentColor,
  help,
  secondary,
}: {
  label: string
  value: string
  tone?: "default" | "positive" | "negative" | "accent"
  accentColor?: string
  help?: string
  secondary?: string
}) {
  return (
    <MetricCard
      label={label}
      value={value}
      tone={tone}
      accentColor={accentColor}
      help={help}
      secondary={secondary}
      compact
      surface="muted"
      className="h-full rounded-[24px]"
      valueClassName="mt-2 text-[1.44rem] font-semibold tracking-[-0.03em]"
    />
  )
}

export function EquityChart({ data }: { data: ChartEquityPoint[] }) {
  if (data.length === 0) {
    return (
      <GlassCard className="p-6">
        <EmptyState
          title="暂无权益曲线"
          description="当前结果还没有足够的权益点可以绘制曲线。"
        />
      </GlassCard>
    )
  }

  const values = data.map((item) => item.equity)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const pad = Math.max((max - min) * 0.12, max * 0.01)

  return (
    <GlassCard className="space-y-4 p-5">
      <PanelHeader
        title="权益曲线"
        description="Y 轴会随当前样本自动缩放，便于观察回撤与趋势切换。"
      />
      <div className="h-[280px]">
        <MeasuredChart height={280}>
          {(width, height) => (
            <AreaChart width={width} height={height} data={data}>
              <defs>
                <linearGradient id="bt-fill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={SONG_COLORS.indigo} stopOpacity={0.22} />
                  <stop offset="100%" stopColor={SONG_COLORS.indigo} stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke={SONG_COLORS.grid} vertical={false} strokeDasharray="3 3" />
              <XAxis dataKey="date" tickLine={false} axisLine={false} minTickGap={36} stroke={SONG_COLORS.axis} />
              <YAxis
                tickLine={false}
                axisLine={false}
                stroke={SONG_COLORS.axis}
                domain={[Math.max(0, min - pad), max + pad]}
                tickFormatter={(value) => `¥${(Number(value) / 1000).toFixed(0)}k`}
              />
              <Tooltip
                formatter={(value) => [formatCurrency(Number(value)), "权益"]}
                labelFormatter={(label) => `日期：${label}`}
                contentStyle={{
                  borderRadius: 18,
                  border: "1px solid var(--chart-tooltip-border)",
                  backgroundColor: "var(--chart-tooltip-bg)",
                }}
              />
              <Area
                type="monotone"
                dataKey="equity"
                stroke={SONG_COLORS.indigo}
                strokeWidth={2.2}
                fill="url(#bt-fill)"
              />
            </AreaChart>
          )}
        </MeasuredChart>
      </div>
    </GlassCard>
  )
}
