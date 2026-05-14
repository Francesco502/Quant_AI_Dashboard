import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { motion } from "framer-motion"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap text-sm font-medium tracking-wide transition-[background-color,border-color,color,box-shadow,transform] duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[rgba(var(--rgb-ochre),0.22)] disabled:pointer-events-none disabled:opacity-40",
  {
    variants: {
      variant: {
        default:
          "rounded-xl bg-[rgb(var(--rgb-celadon))] text-[rgb(var(--rgb-xuan))] shadow-sm hover:bg-[rgba(var(--rgb-celadon),0.9)]",
        destructive:
          "rounded-xl bg-destructive/90 text-destructive-foreground shadow-sm hover:bg-destructive",
        outline:
          "rounded-xl border border-[rgba(var(--rgb-ink),0.1)] dark:border-white/[0.08] bg-[rgba(var(--rgb-xuan),0.84)] dark:bg-white/[0.02] backdrop-blur-md shadow-sm hover:bg-[rgba(var(--rgb-xuan),0.96)] dark:hover:bg-white/[0.05] text-foreground/80 hover:text-foreground",
        secondary:
          "rounded-xl bg-[rgba(var(--rgb-ochre),0.1)] dark:bg-white/[0.04] text-foreground/80 hover:bg-[rgba(var(--rgb-ochre),0.16)] dark:hover:bg-white/[0.08] hover:text-foreground",
        ghost:
          "rounded-xl text-foreground/60 hover:bg-[rgba(var(--rgb-ochre),0.08)] hover:text-foreground dark:hover:bg-white/[0.04]",
        link:
          "text-foreground/60 underline-offset-4 hover:underline hover:text-foreground",
        glass:
          "glass rounded-xl text-foreground/80 hover:text-foreground hover:shadow-md",
      },
      size: {
        default: "min-h-11 px-5 py-2 sm:h-9 sm:min-h-0",
        sm: "min-h-11 px-4 text-xs sm:h-8 sm:min-h-0",
        lg: "min-h-11 px-8 text-sm sm:h-10 sm:min-h-0",
        icon: "h-11 w-11 min-w-11 sm:h-9 sm:w-9 sm:min-w-0",
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
        whileTap={{ scale: 0.985 }}
        transition={{ type: "spring", stiffness: 500, damping: 30 }}
        {...(props as unknown as React.ComponentProps<typeof motion.button>)}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
