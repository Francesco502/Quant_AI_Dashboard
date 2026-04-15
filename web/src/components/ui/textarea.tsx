import * as React from "react"

import { cn } from "@/lib/utils"

export type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement>

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(({ className, ...props }, ref) => {
  return (
    <textarea
      ref={ref}
      className={cn(
        "form-control glass-input flex min-h-32 w-full resize-y px-4 py-3 text-sm",
        "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[rgba(var(--rgb-ochre),0.5)] focus-visible:border-[rgba(var(--rgb-ochre),0.8)]",
        "disabled:cursor-not-allowed disabled:opacity-40",
        className,
      )}
      {...props}
    />
  )
})

Textarea.displayName = "Textarea"

export { Textarea }
