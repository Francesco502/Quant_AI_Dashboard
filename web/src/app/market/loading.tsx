import { CardSkeleton } from "@/components/ui/skeleton"

export default function MarketLoading() {
  return (
    <div className="space-y-8" role="status" aria-label="页面加载中">
      <CardSkeleton rows={3} />
      <div className="grid gap-6 md:grid-cols-2">
        <CardSkeleton rows={4} />
        <CardSkeleton rows={4} />
      </div>
      <CardSkeleton rows={5} />
      <span className="sr-only">正在载入市场分析数据...</span>
    </div>
  )
}
