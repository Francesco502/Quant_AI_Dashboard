"use client"

import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { Button, type ButtonProps } from "@/components/ui/button"
import { cn } from "@/lib/utils"

const iconButtonVariants = cva("icon-button-shell p-0", {
  variants: {
    variant: {
      ghost: "icon-button-ghost",
      subtle: "icon-button-subtle",
      outline: "icon-button-outline",
      danger: "icon-button-danger",
    },
    size: {
      sm: "icon-button-sm",
      md: "icon-button-md",
      lg: "icon-button-lg",
    },
  },
  defaultVariants: {
    variant: "ghost",
    size: "md",
  },
})

export interface IconButtonProps
  extends Omit<ButtonProps, "size" | "variant">,
    VariantProps<typeof iconButtonVariants> {
  icon?: React.ReactNode
  label: string
}

export function IconButton({
  className,
  variant,
  size,
  icon,
  label,
  asChild = false,
  children,
  ...props
}: IconButtonProps) {
  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      className={cn(iconButtonVariants({ variant, size }), className)}
      aria-label={label}
      title={label}
      asChild={asChild}
      {...props}
    >
      {asChild ? children : icon}
    </Button>
  )
}
