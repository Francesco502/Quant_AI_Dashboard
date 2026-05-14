import { CardSkeleton } from "@/components/ui/skeleton"

export default function HomeLoading() {
  return (
    <div className="space-y-8" role="status" aria-label="页面加载中">
      <div className="flex items-center gap-4">
        <div className="h-10 w-48 animate-pulse rounded-2xl bg-muted/60" />
        <div className="h-5 w-32 animate-pulse rounded-xl bg-muted/40" />
      </div>
      <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-4">
        <CardSkeleton rows={2} />
        <CardSkeleton rows={2} />
        <CardSkeleton rows={2} />
        <CardSkeleton rows={2} />
      </div>
      <CardSkeleton rows={5} />
      <span className="sr-only">正在载入总览数据...</span>
    </div>
  )
}
