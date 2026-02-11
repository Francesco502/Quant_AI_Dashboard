import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

/* ----------------------------------------------------------------
   Badge — Subtle pill labels with frosted glass variants
   ---------------------------------------------------------------- */
const badgeVariants = cva(
  "inline-flex items-center rounded-lg border px-2 py-0.5 text-[11px] font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-ring/20 focus:ring-offset-1",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-foreground/90 text-background",
        secondary:
          "border-black/[0.06] dark:border-white/[0.08] bg-black/[0.04] dark:bg-white/[0.06] text-foreground/70",
        destructive:
          "border-transparent bg-red-500/10 text-red-600 dark:text-red-400",
        outline:
          "border-black/[0.08] dark:border-white/[0.1] text-foreground/60",
        success:
          "border-transparent bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge, badgeVariants }
