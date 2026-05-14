import * as React from "react"

import { cn } from "@/lib/utils"

/* ----------------------------------------------------------------
   Input — Frosted glass field with inset shadow for depth
   ---------------------------------------------------------------- */
export type InputProps = React.InputHTMLAttributes<HTMLInputElement>

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          "glass-input flex min-h-11 w-full rounded-xl px-3 py-2 text-sm sm:h-9 sm:min-h-0 sm:py-1.5",
          "placeholder:text-foreground/30",
          "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[rgba(var(--rgb-ochre),0.5)] focus-visible:border-[rgba(var(--rgb-ochre),0.8)]",
          "disabled:cursor-not-allowed disabled:opacity-40",
          "file:border-0 file:bg-transparent file:text-sm file:font-medium",
          className
        )}
        ref={ref}
        {...props}
      />
    )
  }
)
Input.displayName = "Input"

export { Input }
