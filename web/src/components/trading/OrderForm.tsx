"use client"

import React from "react"

import { FormField } from "@/components/form/form-field"
import { NoteBlock } from "@/components/data/note-block"
import { StatusNotice } from "@/components/data/status-notice"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { HelpTooltip } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

export type OrderType = "MARKET" | "LIMIT" | "STOP" | "STOP_LIMIT"
export type OrderSide = "BUY" | "SELL"

interface OrderFormProps {
  ticker: string
  current_price: number
  balance: number
  position: number
  onSubmit: (order: OrderRequest) => void
  onCancel?: () => void
}

export interface OrderRequest {
  ticker: string
  side: OrderSide
  order_type: OrderType
  quantity: number
  price?: number
  stop_price?: number
}

const ORDER_TYPE_LABELS: Record<OrderType, string> = {
  MARKET: "市价",
  LIMIT: "限价",
  STOP: "止损",
  STOP_LIMIT: "止损限价",
}

function activeTone(side: OrderSide) {
  return side === "BUY"
    ? "border-[rgba(var(--rgb-cinnabar),0.14)] bg-[rgba(var(--rgb-cinnabar),0.07)] text-tone-positive"
    : "border-[rgba(var(--rgb-celadon),0.14)] bg-[rgba(var(--rgb-celadon),0.07)] text-tone-negative"
}

export function OrderForm({ ticker, current_price, balance, position, onSubmit, onCancel }: OrderFormProps) {
  const [side, setSide] = React.useState<OrderSide>("BUY")
  const [order_type, setOrderType] = React.useState<OrderType>("MARKET")
  const [quantity, setQuantity] = React.useState<string>("")
  const [price, setPrice] = React.useState<string>("")
  const [stop_price, setStopPrice] = React.useState<string>("")
  const [error, setError] = React.useState<string>("")

  const estimatedValue = () => {
    const qty = parseInt(quantity, 10) || 0
    if (side === "BUY") {
      if (order_type === "LIMIT" && price) {
        return qty * parseFloat(price)
      }
      return qty * current_price
    }
    return qty * current_price
  }

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    setError("")

    const qty = parseInt(quantity, 10)
    if (Number.isNaN(qty) || qty <= 0) {
      setError("请输入有效的数量。")
      return
    }

    if (order_type === "LIMIT" && (!price || parseFloat(price) <= 0)) {
      setError("限价单需要有效的委托价格。")
      return
    }

    if (order_type === "STOP" && (!stop_price || parseFloat(stop_price) <= 0)) {
      setError("止损单需要有效的触发价格。")
      return
    }

    const order: OrderRequest = {
      ticker,
      side,
      order_type,
      quantity: qty,
      price: order_type === "LIMIT" ? parseFloat(price) : undefined,
      stop_price: order_type === "STOP" ? parseFloat(stop_price) : undefined,
    }

    onSubmit(order)
  }

  const canAfford = () => {
    if (side === "BUY") {
      return balance >= estimatedValue()
    }
    return position >= (parseInt(quantity, 10) || 0)
  }

  const affordable = canAfford()
  const showEstimate = quantity.trim().length > 0

  return (
    <Card className="w-full">
      <CardHeader className="space-y-2">
        <CardTitle className="flex items-center gap-2">
          手动下单
          <HelpTooltip
            content={`当前价格：¥${current_price.toFixed(2)}；可用资金：¥${balance.toLocaleString()}；当前持仓：${position} 股`}
          />
        </CardTitle>
        <p className="text-sm leading-7 text-foreground/68">围绕 {ticker} 创建手动模拟订单，保留买卖方向、价格条件和仓位约束。</p>
      </CardHeader>

      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="grid grid-cols-2 gap-2.5">
            {(["BUY", "SELL"] as OrderSide[]).map((value) => {
              const active = side === value
              return (
                <button
                  key={value}
                  type="button"
                  onClick={() => setSide(value)}
                  className={cn(
                    "rounded-2xl border px-4 py-3 text-sm font-medium transition-[background-color,border-color,color,box-shadow] duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]",
                    active
                      ? activeTone(value)
                      : "border-black/[0.06] bg-[rgba(var(--rgb-xuan),0.72)] text-foreground/72 hover:bg-[rgba(var(--rgb-xuan),0.92)] hover:text-foreground/88",
                  )}
                >
                  {value === "BUY" ? "买入" : "卖出"}
                </button>
              )
            })}
          </div>

          <FormField label="订单类型" description="选择市价、限价或带触发条件的模拟委托。">
            <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
              {(Object.keys(ORDER_TYPE_LABELS) as OrderType[]).map((type) => {
                const active = order_type === type
                return (
                  <button
                    key={type}
                    type="button"
                    onClick={() => setOrderType(type)}
                    className={cn(
                      "rounded-2xl border px-3 py-2.5 text-[0.82rem] font-medium transition-[background-color,border-color,color,box-shadow] duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]",
                      active
                        ? "border-[rgba(var(--rgb-indigo),0.18)] bg-[rgba(var(--rgb-indigo),0.1)] text-tone-indigo"
                        : "border-black/[0.06] bg-[rgba(var(--rgb-xuan),0.68)] text-foreground/68 hover:bg-[rgba(var(--rgb-xuan),0.92)] hover:text-foreground/84",
                    )}
                  >
                    {ORDER_TYPE_LABELS[type]}
                  </button>
                )
              })}
            </div>
          </FormField>

          <div className="grid gap-4 md:grid-cols-2">
            <FormField label="数量" description="请输入本次模拟委托的股数。">
              <Input
                type="number"
                value={quantity}
                onChange={(event) => setQuantity(event.target.value)}
                placeholder="请输入数量"
                min="1"
                className="font-mono"
              />
            </FormField>

            {(order_type === "LIMIT" || order_type === "STOP_LIMIT") && (
              <FormField
                label="限价"
                description={order_type === "LIMIT" ? "到达指定价格后成交。" : "触发后按该限价挂单。"}
              >
                <Input
                  type="number"
                  value={price}
                  onChange={(event) => setPrice(event.target.value)}
                  placeholder={`参考 ${current_price.toFixed(2)}`}
                  step="0.01"
                  className="font-mono"
                />
              </FormField>
            )}
          </div>

          {(order_type === "STOP" || order_type === "STOP_LIMIT") && (
            <FormField
              label="触发价"
              description={order_type === "STOP" ? "触发后转为市价委托。" : "到达触发价后再按上方限价挂单。"}
            >
              <Input
                type="number"
                value={stop_price}
                onChange={(event) => setStopPrice(event.target.value)}
                placeholder="请输入触发价格"
                step="0.01"
                className="font-mono"
              />
            </FormField>
          )}

          {showEstimate ? (
            <StatusNotice tone={affordable ? "success" : "warning"} title={side === "BUY" ? "预计成本" : "预计回笼"}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-semibold">¥{estimatedValue().toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                <span>{affordable ? "资金或仓位满足当前委托。" : "当前资金或仓位不足，请调整数量或价格条件。"}</span>
              </div>
            </StatusNotice>
          ) : null}

          {order_type === "STOP" ? (
            <NoteBlock title="止损说明" tone="accent" muted>
              多头止损通常在价格跌破触发位后执行平仓，适合为已有持仓设置保护。
            </NoteBlock>
          ) : null}

          {error ? (
            <StatusNotice tone="error" title="订单校验未通过">
              {error}
            </StatusNotice>
          ) : null}

          <div className="flex gap-3 pt-1">
            <Button type="submit" className="flex-1">
              {side === "BUY" ? "提交买入订单" : "提交卖出订单"}
            </Button>
            {onCancel ? (
              <Button type="button" variant="outline" onClick={onCancel}>
                取消
              </Button>
            ) : null}
          </div>
        </form>
      </CardContent>
    </Card>
  )
}
