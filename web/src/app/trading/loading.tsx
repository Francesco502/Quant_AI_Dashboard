import { CardSkeleton } from "@/components/ui/skeleton"

export default function TradingLoading() {
  return (
    <div className="space-y-8" role="status" aria-label="页面加载中">
      <CardSkeleton rows={3} />
      <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
        <CardSkeleton rows={2} />
        <CardSkeleton rows={2} />
        <CardSkeleton rows={2} />
      </div>
      <CardSkeleton rows={6} />
      <span className="sr-only">正在载入模拟交易数据...</span>
    </div>
  )
}
