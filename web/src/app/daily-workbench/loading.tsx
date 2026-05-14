import { CardSkeleton } from "@/components/ui/skeleton"

export default function DailyWorkbenchLoading() {
  return (
    <div className="space-y-8" role="status" aria-label="页面加载中">
      <CardSkeleton rows={3} />
      <div className="grid gap-6 md:grid-cols-2">
        <CardSkeleton rows={3} />
        <CardSkeleton rows={3} />
      </div>
      <CardSkeleton rows={4} />
      <span className="sr-only">正在载入日常决策数据...</span>
    </div>
  )
}
