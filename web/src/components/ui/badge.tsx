import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

/* ----------------------------------------------------------------
   Badge — Subtle pill labels with frosted glass variants
   ---------------------------------------------------------------- */
const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-1 text-[0.74rem] font-semibold leading-none tracking-normal backdrop-blur-md transition-all duration-200 shadow-[0_2px_8px_rgba(0,0,0,0.02)] dark:shadow-[0_2px_8px_rgba(0,0,0,0.12)] focus:outline-none focus:ring-2 focus:ring-ring/20 focus:ring-offset-1",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-foreground/90 text-background",
        secondary:
          "border-black/[0.06] dark:border-white/[0.08] bg-black/[0.04] dark:bg-white/[0.06] text-foreground/76",
        destructive:
          "border-[rgba(var(--rgb-cinnabar),0.16)] bg-[rgba(var(--rgb-cinnabar),0.1)] text-[rgba(var(--rgb-cinnabar),0.96)]",
        outline:
          "border-black/[0.08] dark:border-white/[0.1] bg-[rgba(var(--rgb-xuan),0.52)] text-foreground/72",
        success:
          "border-[rgba(var(--rgb-celadon),0.16)] bg-[rgba(var(--rgb-celadon),0.1)] text-[rgba(var(--rgb-celadon),0.96)]",
        warning:
          "border-[rgba(var(--rgb-ochre),0.18)] bg-[rgba(var(--rgb-ochre),0.11)] text-[rgba(120,94,59,0.96)]",
        info:
          "border-[rgba(var(--rgb-indigo),0.16)] bg-[rgba(var(--rgb-indigo),0.1)] text-[rgba(76,88,105,0.96)]",
        accent:
          "border-[rgba(var(--rgb-plum),0.16)] bg-[rgba(var(--rgb-plum),0.1)] text-[rgba(109,92,102,0.96)]",
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
