"use client"

import { cn } from "@/lib/utils"

type BrandMarkProps = {
  className?: string
  iconClassName?: string
}

export function BrandMark({ className, iconClassName }: BrandMarkProps) {
  return (
    <div
      className={cn(
        "flex h-11 w-11 items-center justify-center rounded-[18px] border border-[rgba(var(--rgb-ochre),0.18)] bg-[linear-gradient(145deg,rgba(252,249,244,0.98),rgba(240,232,220,0.96))] shadow-[0_12px_28px_rgba(46,38,30,0.05)]",
        className,
      )}
      aria-hidden="true"
    >
      <svg
        viewBox="0 0 48 48"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className={cn("h-6.5 w-6.5", iconClassName)}
      >
        <rect x="9" y="25" width="5" height="10" rx="2.5" fill="rgb(var(--rgb-ink))" fillOpacity="0.9" />
        <rect x="18.5" y="20" width="5" height="15" rx="2.5" fill="rgb(var(--rgb-ink))" fillOpacity="0.9" />
        <rect x="28" y="15" width="5" height="20" rx="2.5" fill="rgb(var(--rgb-ink))" fillOpacity="0.9" />
        <path
          d="M10 18.5C13.1 20.1 16.3 20.3 19.6 19C23 17.7 26.4 15.1 30 11.2L35.5 6"
          stroke="rgb(var(--rgb-ochre))"
          strokeWidth="3.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <circle cx="36.5" cy="6.5" r="3.2" fill="rgb(var(--rgb-celadon))" />
      </svg>
    </div>
  )
}
