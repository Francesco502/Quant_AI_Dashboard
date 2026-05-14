import { CardSkeleton } from "@/components/ui/skeleton"

export default function PortfolioLoading() {
  return (
    <div className="space-y-8" role="status" aria-label="页面加载中">
      <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-4">
        <CardSkeleton rows={2} />
        <CardSkeleton rows={2} />
        <CardSkeleton rows={2} />
        <CardSkeleton rows={2} />
      </div>
      <CardSkeleton rows={5} />
      <span className="sr-only">正在载入资产组合数据...</span>
    </div>
  )
}
