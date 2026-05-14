import { CardSkeleton } from "@/components/ui/skeleton"

export default function LoginLoading() {
  return (
    <div className="mx-auto flex min-h-[60vh] max-w-md items-center" role="status">
      <CardSkeleton rows={4} />
      <span className="sr-only">正在载入...</span>
    </div>
  )
}
