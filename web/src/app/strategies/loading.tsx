import { CardSkeleton } from "@/components/ui/skeleton"

export default function StrategiesLoading() {
  return (
    <div className="space-y-8" role="status" aria-label="页面加载中">
      <CardSkeleton rows={3} />
      <CardSkeleton rows={5} />
      <span className="sr-only">正在载入量化策略数据...</span>
    </div>
  )
}
