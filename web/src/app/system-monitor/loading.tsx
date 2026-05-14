import { CardSkeleton } from "@/components/ui/skeleton"

export default function SystemMonitorLoading() {
  return (
    <div className="space-y-8" role="status" aria-label="页面加载中">
      <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-4">
        <CardSkeleton rows={2} />
        <CardSkeleton rows={2} />
        <CardSkeleton rows={2} />
        <CardSkeleton rows={2} />
      </div>
      <CardSkeleton rows={3} />
      <CardSkeleton rows={4} />
      <span className="sr-only">正在载入系统监控数据...</span>
    </div>
  )
}
