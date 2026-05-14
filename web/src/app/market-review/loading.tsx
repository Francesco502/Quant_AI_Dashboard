import { CardSkeleton } from "@/components/ui/skeleton"

export default function MarketReviewLoading() {
  return (
    <div className="space-y-8" role="status" aria-label="页面加载中">
      <CardSkeleton rows={5} />
      <CardSkeleton rows={4} />
      <span className="sr-only">正在载入大盘复盘数据...</span>
    </div>
  )
}
