"use client"

import React from 'react'
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { HelpTooltip } from "@/components/ui/tooltip"

// 订单类型定义
export type OrderType = 'MARKET' | 'LIMIT' | 'STOP' | 'STOP_LIMIT'
export type OrderSide = 'BUY' | 'SELL'

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

export function OrderForm({ ticker, current_price, balance, position, onSubmit, onCancel }: OrderFormProps) {
  const [side, setSide] = React.useState<OrderSide>('BUY')
  const [order_type, setOrderType] = React.useState<OrderType>('MARKET')
  const [quantity, setQuantity] = React.useState<string>('')
  const [price, setPrice] = React.useState<string>('')
  const [stop_price, setStopPrice] = React.useState<string>('')
  const [error, setError] = React.useState<string>('')

  // 预估成本/收入
  const estimatedValue = () => {
    const qty = parseInt(quantity) || 0
    if (side === 'BUY') {
      if (order_type === 'LIMIT' && price) {
        return qty * parseFloat(price)
      }
      return qty * current_price
    } else {
      return qty * current_price
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    const qty = parseInt(quantity)
    if (isNaN(qty) || qty <= 0) {
      setError('请输入有效的数量')
      return
    }

    // 验证价格
    if (order_type === 'LIMIT' && (!price || parseFloat(price) <= 0)) {
      setError('限价单需要有效的价格')
      return
    }

    if (order_type === 'STOP' && (!stop_price || parseFloat(stop_price) <= 0)) {
      setError('止损单需要有效的触发价')
      return
    }

    const order: OrderRequest = {
      ticker,
      side,
      order_type,
      quantity: qty,
      price: order_type === 'LIMIT' ? parseFloat(price) : undefined,
      stop_price: order_type === 'STOP' ? parseFloat(stop_price) : undefined
    }

    onSubmit(order)
  }

  // 资金/持仓检查
  const canAfford = () => {
    if (side === 'BUY') {
      return balance >= estimatedValue()
    }
    return position >= parseInt(quantity) || parseInt(quantity) === 0
  }

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          下单交易
          <HelpTooltip content={`当前价格: ¥${current_price.toFixed(2)} | 可用资金: ¥${balance.toLocaleString()} | 持仓: ${position} 股`} />
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* 订单方向 */}
          <div className="flex gap-2">
            <Button
              type="button"
              onClick={() => setSide('BUY')}
              className={`flex-1 py-3 ${side === 'BUY' ? 'bg-green-600 hover:bg-green-700 text-white' : 'bg-gray-100 hover:bg-gray-200'}`}
            >
              买入
            </Button>
            <Button
              type="button"
              onClick={() => setSide('SELL')}
              className={`flex-1 py-3 ${side === 'SELL' ? 'bg-red-600 hover:bg-red-700 text-white' : 'bg-gray-100 hover:bg-gray-200'}`}
            >
              卖出
            </Button>
          </div>

          {/* 订单类型 */}
          <div className="grid grid-cols-4 gap-2">
            {(['MARKET', 'LIMIT', 'STOP', 'STOP_LIMIT'] as OrderType[]).map(type => (
              <Button
                key={type}
                type="button"
                onClick={() => setOrderType(type)}
                className={`py-2 px-2 text-xs rounded-md ${
                  order_type === type
                    ? 'bg-blue-600 hover:bg-blue-700 text-white'
                    : 'bg-gray-100 hover:bg-gray-200 text-gray-600'
                }`}
              >
                {type === 'MARKET' ? '市价' : type === 'LIMIT' ? '限价' : type === 'STOP' ? '止损' : '止盈'}
              </Button>
            ))}
          </div>

          {/* 输入字段 */}
          <div className="space-y-3">
            <div className="space-y-1">
              <Label className="text-sm">数量</Label>
              <Input
                type="number"
                value={quantity}
                onChange={e => setQuantity(e.target.value)}
                placeholder="请输入数量"
                min="1"
                className="font-mono"
              />
            </div>

            {order_type === 'LIMIT' && (
              <div className="space-y-1">
                <Label className="text-sm">限价</Label>
                <Input
                  type="number"
                  value={price}
                  onChange={e => setPrice(e.target.value)}
                  placeholder={`当前价: ${current_price}`}
                  step="0.01"
                  className="font-mono"
                />
                <p className="text-xs text-muted-foreground">
                  限价买入: ≤指定价格成交 | 限价卖出: ≥指定价格成交
                </p>
              </div>
            )}

            {order_type === 'STOP' && (
              <div className="space-y-1">
                <Label className="text-sm">触发价</Label>
                <Input
                  type="number"
                  value={stop_price}
                  onChange={e => setStopPrice(e.target.value)}
                  placeholder="触发后转市价单"
                  step="0.01"
                  className="font-mono"
                />
                <p className="text-xs text-muted-foreground">
                  多头止损: 价格 ≤ 触发价时平仓
                </p>
              </div>
            )}

            {order_type === 'STOP_LIMIT' && (
              <div className="space-y-1">
                <Label className="text-sm">触发价</Label>
                <Input
                  type="number"
                  value={stop_price}
                  onChange={e => setStopPrice(e.target.value)}
                  placeholder="触发后转限价单"
                  step="0.01"
                  className="font-mono"
                />
                <Label className="text-sm mt-2">限价</Label>
                <Input
                  type="number"
                  value={price}
                  onChange={e => setPrice(e.target.value)}
                  placeholder="限价"
                  step="0.01"
                  className="font-mono"
                />
                <p className="text-xs text-muted-foreground">
                  触发后以限价平仓
                </p>
              </div>
            )}
          </div>

          {/* 预估信息 */}
          {quantity && (
            <div className={`text-sm p-3 rounded-lg ${
              side === 'BUY'
                ? canAfford() ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
                : canAfford() ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
            }`}>
              <div className="flex justify-between items-center">
                <span>
                  {side === 'BUY' ? '预估成本' : '预估收入'}:
                  <span className="font-bold ml-1">¥{estimatedValue().toLocaleString(undefined, {minimumFractionDigits: 2})}</span>
                </span>
                {canAfford() ? (
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-green-500" />
                    充足
                  </span>
                ) : (
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-red-500" />
                    不足
                  </span>
                )}
              </div>
            </div>
          )}

          {/* 错误提示 */}
          {error && (
            <div className="text-red-600 text-sm bg-red-50 p-3 rounded-lg flex items-center gap-2">
              <span className="font-semibold">错误:</span> {error}
            </div>
          )}

          {/* 操作按钮 */}
          <div className="flex gap-3 mt-4">
            <Button
              type="submit"
              className={`flex-1 py-3 text-base font-semibold ${
                side === 'BUY'
                  ? 'bg-green-600 hover:bg-green-700 text-white'
                  : 'bg-red-600 hover:bg-red-700 text-white'
              }`}
            >
              {side === 'BUY' ? '买入下单' : '卖出下单'}
            </Button>
            {onCancel && (
              <Button
                type="button"
                variant="outline"
                onClick={onCancel}
              >
                取消
              </Button>
            )}
          </div>
        </form>
      </CardContent>
    </Card>
  )
}
