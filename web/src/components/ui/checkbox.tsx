"use client"

import * as React from "react"
import * as CheckboxPrimitive from "@radix-ui/react-checkbox"
import { Check } from "lucide-react"

import { cn } from "@/lib/utils"

/* ----------------------------------------------------------------
   Checkbox — Subtle glass checkbox with smooth check animation
   ---------------------------------------------------------------- */
const Checkbox = React.forwardRef<
  React.ElementRef<typeof CheckboxPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof CheckboxPrimitive.Root>
>(({ className, ...props }, ref) => (
  <CheckboxPrimitive.Root
    ref={ref}
    className={cn(
      "peer h-4 w-4 shrink-0 rounded-[5px]",
      "border border-black/[0.12] dark:border-white/[0.15]",
      "bg-white/50 dark:bg-white/[0.04]",
      "shadow-[inset_0_1px_2px_rgba(0,0,0,0.04)]",
      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/20 focus-visible:ring-offset-1",
      "disabled:cursor-not-allowed disabled:opacity-40",
      "data-[state=checked]:bg-foreground data-[state=checked]:text-background",
      "data-[state=checked]:border-transparent",
      "transition-all duration-200",
      className
    )}
    {...props}
  >
    <CheckboxPrimitive.Indicator
      className={cn("flex items-center justify-center text-current")}
    >
      <Check className="h-3 w-3" strokeWidth={2.5} />
    </CheckboxPrimitive.Indicator>
  </CheckboxPrimitive.Root>
))
Checkbox.displayName = CheckboxPrimitive.Root.displayName

export { Checkbox }
