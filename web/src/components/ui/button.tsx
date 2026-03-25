import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { motion } from "framer-motion"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap text-[13px] font-medium transition-all duration-300 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-40 tracking-wide",
  {
    variants: {
      variant: {
        default:
          "rounded-xl bg-[#6B8E7B] text-[#FAF9F6] shadow-sm hover:bg-[#5A7A68]",
        destructive:
          "rounded-xl bg-destructive/90 text-destructive-foreground shadow-sm hover:bg-destructive",
        outline:
          "rounded-xl border border-black/[0.06] dark:border-white/[0.08] bg-[rgba(250,249,246,0.5)] dark:bg-white/[0.02] backdrop-blur-md shadow-sm hover:bg-[#FAF9F6] dark:hover:bg-white/[0.05] text-foreground/80 hover:text-foreground",
        secondary:
          "rounded-xl bg-[#E8E6E1] dark:bg-white/[0.04] text-foreground/80 hover:bg-[#DFDCD6] dark:hover:bg-white/[0.08] hover:text-foreground",
        ghost:
          "rounded-xl text-foreground/60 hover:text-foreground hover:bg-[#E8E6E1]/50 dark:hover:bg-white/[0.04]",
        link:
          "text-foreground/60 underline-offset-4 hover:underline hover:text-foreground",
        glass:
          "glass rounded-xl text-foreground/80 hover:text-foreground hover:shadow-md",
      },
      size: {
        default: "h-9 px-5 py-2",
        sm: "h-8 px-4 text-[12px]",
        lg: "h-10 px-8 text-sm",
        icon: "h-9 w-9",
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

