import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { motion } from "framer-motion"

import { cn } from "@/lib/utils"

/* ----------------------------------------------------------------
   Button — Skeuominimalism: subtle physical feel with press states
   ---------------------------------------------------------------- */
const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap text-[13px] font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/20 focus-visible:ring-offset-1 disabled:pointer-events-none disabled:opacity-40",
  {
    variants: {
      variant: {
        default:
          "bg-foreground text-background rounded-xl shadow-[0_1px_2px_rgba(0,0,0,0.15),inset_0_1px_0_rgba(255,255,255,0.1)] hover:bg-foreground/90 active:shadow-[inset_0_1px_3px_rgba(0,0,0,0.2)]",
        destructive:
          "bg-destructive text-destructive-foreground rounded-xl shadow-[0_1px_2px_rgba(0,0,0,0.1)] hover:bg-destructive/90",
        outline:
          "rounded-xl border border-black/[0.08] dark:border-white/[0.1] bg-white/50 dark:bg-white/[0.04] backdrop-blur-sm shadow-[0_1px_2px_rgba(0,0,0,0.04)] hover:bg-white/80 dark:hover:bg-white/[0.07] hover:border-black/[0.12] dark:hover:border-white/[0.14] text-foreground/80 hover:text-foreground",
        secondary:
          "bg-black/[0.04] dark:bg-white/[0.06] text-foreground/70 rounded-xl hover:bg-black/[0.07] dark:hover:bg-white/[0.09] hover:text-foreground",
        ghost:
          "rounded-xl text-foreground/50 hover:text-foreground/80 hover:bg-black/[0.04] dark:hover:bg-white/[0.06]",
        link:
          "text-foreground/60 underline-offset-4 hover:underline hover:text-foreground",
        glass:
          "glass rounded-xl text-foreground/80 hover:text-foreground hover:shadow-[0_2px_8px_rgba(0,0,0,0.06)]",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-7 px-3 text-[12px]",
        lg: "h-10 px-6 text-sm",
        icon: "h-8 w-8",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    if (asChild) {
      return (
        <Slot
          className={cn(buttonVariants({ variant, size, className }))}
          ref={ref}
          {...props}
        />
      )
    }

    return (
      <motion.button
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        whileTap={{ scale: 0.97 }}
        transition={{ type: "spring", stiffness: 500, damping: 30 }}
        {...(props as any)}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
