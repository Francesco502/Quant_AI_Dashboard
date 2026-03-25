"use client"

import { type ReactNode, useEffect, useRef, useState } from "react"

export function MeasuredChart({
  height,
  children,
}: {
  height: number
  children: (width: number, height: number) => ReactNode
}) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [width, setWidth] = useState(0)

  useEffect(() => {
    const node = containerRef.current
    if (!node) return

    const updateWidth = () => {
      const nextWidth = Math.max(Math.floor(node.getBoundingClientRect().width), 0)
      setWidth(nextWidth)
    }

    updateWidth()
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(() => updateWidth()) : null
    observer?.observe(node)
    window.addEventListener("resize", updateWidth)

    return () => {
      observer?.disconnect()
      window.removeEventListener("resize", updateWidth)
    }
  }, [])

  return (
    <div ref={containerRef} className="min-w-0 w-full" style={{ height }}>
      {width > 0 ? children(width, height) : null}
    </div>
  )
}
