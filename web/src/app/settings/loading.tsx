import { CardSkeleton } from "@/components/ui/skeleton"

export default function SettingsLoading() {
  return (
    <div className="space-y-8" role="status" aria-label="页面加载中">
      <CardSkeleton rows={4} />
      <CardSkeleton rows={3} />
      <span className="sr-only">正在载入系统设置...</span>
    </div>
  )
}
