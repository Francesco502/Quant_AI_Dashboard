import { CardSkeleton } from "@/components/ui/skeleton"

export default function MarketScannerLoading() {
  return (
    <div className="space-y-8" role="status" aria-label="页面加载中">
      <CardSkeleton rows={3} />
      <CardSkeleton rows={5} />
      <span className="sr-only">正在载入市场扫描数据...</span>
    </div>
  )
}
