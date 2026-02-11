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
          "flex h-9 w-full rounded-xl px-3 py-1.5 text-[13px]",
          "glass-input",
          "placeholder:text-foreground/30",
          "focus-visible:outline-none",
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
