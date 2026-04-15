import * as React from "react"
import { motion, HTMLMotionProps } from "framer-motion"

import { cn } from "@/lib/utils"

const Card = React.forwardRef<
  HTMLDivElement,
  HTMLMotionProps<"div">
>(({ className, ...props }, ref) => (
  <motion.div
    ref={ref}
    className={cn(
      "rounded-[24px] border border-[rgba(77,71,66,0.08)] dark:border-white/[0.05]",
      "bg-[rgba(250,246,239,0.88)] dark:bg-[rgba(30,28,26,0.7)]",
      "backdrop-blur-xl shadow-[0_14px_36px_rgba(41,33,25,0.06)]",
      "text-card-foreground",
      className
    )}
    {...props}
  />
))
Card.displayName = "Card"

const CardHeader = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex flex-col space-y-1.5 p-6 pb-4", className)}
    {...props}
  />
))
CardHeader.displayName = "CardHeader"

const CardTitle = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h3
    ref={ref}
    className={cn(
        "font-serif text-[1.22rem] font-semibold leading-[1.34] tracking-[0.02em] text-foreground/92",
      className
    )}
    {...props}
  />
))
CardTitle.displayName = "CardTitle"

const CardDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p
    ref={ref}
    className={cn("text-[14px] leading-7 tracking-[0.018em] text-foreground/72", className)}
    {...props}
  />
))
CardDescription.displayName = "CardDescription"

const CardContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("p-6 pt-0", className)} {...props} />
))
CardContent.displayName = "CardContent"

const CardFooter = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex items-center p-6 pt-0", className)}
    {...props}
  />
))
CardFooter.displayName = "CardFooter"

const GlassCard = React.forwardRef<
  HTMLDivElement,
  HTMLMotionProps<"div">
>(({ className, ...props }, ref) => (
  <motion.div
    ref={ref}
    whileHover={{ y: -1, transition: { duration: 0.28, ease: [0.16, 1, 0.3, 1] } }}
    className={cn(
      "rounded-[24px] border border-[rgba(var(--rgb-ink),0.08)] bg-[rgba(var(--rgb-xuan),0.84)] p-6 backdrop-blur-md shadow-[0_12px_30px_rgba(41,33,25,0.05)] transition-[background-color,border-color,box-shadow,transform] duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]",
      className
    )}
    {...props}
  />
))
GlassCard.displayName = "GlassCard"

export { Card, CardHeader, CardFooter, CardTitle, CardDescription, CardContent, GlassCard }
