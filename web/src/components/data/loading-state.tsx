"use client"

import { LoaderCircle } from "lucide-react"

import { cn } from "@/lib/utils"

type LoadingStateProps = {
  title?: string
  description?: string
  inline?: boolean
  size?: "sm" | "md" | "lg"
  className?: string
}

export function LoadingState({
  title = "正在加载",
  description,
  inline = false,
  size = "md",
  className,
}: LoadingStateProps) {
  return (
    <div className={cn("loading-state", inline ? "loading-state-inline" : "loading-state-panel", className)}>
      <div className={cn("loading-spinner", `loading-spinner-${size}`)}>
        <LoaderCircle className={cn(size === "lg" ? "h-5 w-5" : "h-4 w-4", "animate-spin")} />
      </div>
      <div className={cn("space-y-1", inline ? "text-left" : "")}>
        <div className="loading-state-title">{title}</div>
        {description ? <div className="loading-state-description">{description}</div> : null}
      </div>
    </div>
  )
}
