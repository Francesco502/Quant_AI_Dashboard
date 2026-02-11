"use client"

import * as React from "react"
import * as TooltipPrimitive from "@radix-ui/react-tooltip"

import { cn } from "@/lib/utils"

/* ----------------------------------------------------------------
   Tooltip — Frosted glass floating label
   ---------------------------------------------------------------- */

const TooltipProvider = TooltipPrimitive.Provider
const Tooltip = TooltipPrimitive.Root
const TooltipTrigger = TooltipPrimitive.Trigger

const TooltipContent = React.forwardRef<
  React.ElementRef<typeof TooltipPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>
>(({ className, sideOffset = 4, ...props }, ref) => (
  <TooltipPrimitive.Portal>
    <TooltipPrimitive.Content
      ref={ref}
      sideOffset={sideOffset}
      className={cn(
        "z-50 overflow-hidden rounded-lg px-3 py-1.5 text-[12px]",
        "glass-dropdown",
        "text-foreground/80",
        "animate-in fade-in-0 zoom-in-[0.98]",
        "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-[0.98]",
        "data-[side=bottom]:slide-in-from-top-1 data-[side=left]:slide-in-from-right-1",
        "data-[side=right]:slide-in-from-left-1 data-[side=top]:slide-in-from-bottom-1",
        className
      )}
      {...props}
    />
  </TooltipPrimitive.Portal>
))
TooltipContent.displayName = TooltipPrimitive.Content.displayName

const HelpTooltip = ({ content, className }: { content: string, className?: string }) => {
  return (
    <TooltipProvider>
      <Tooltip delayDuration={300}>
        <TooltipTrigger asChild>
          <span
            className={cn(
              "inline-flex items-center justify-center w-3.5 h-3.5 rounded-full",
              "border border-foreground/15 text-foreground/30",
              "text-[9px] cursor-help",
              "hover:bg-black/[0.04] dark:hover:bg-white/[0.06]",
              "hover:text-foreground/50 hover:border-foreground/25",
              "transition-all duration-150 ml-1",
              className
            )}
          >
            ?
          </span>
        </TooltipTrigger>
        <TooltipContent>
          <p className="max-w-xs leading-relaxed">{content}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

export { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider, HelpTooltip }
