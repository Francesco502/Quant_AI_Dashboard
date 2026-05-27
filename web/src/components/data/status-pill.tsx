"use client"

import { type ComponentType } from "react"

import { cn } from "@/lib/utils"

type Tone = "ink" | "indigo" | "plum" | "celadon" | "ochre" | "cinnabar"

const toneClasses: Record<Tone, string> = {
  ink: "surface-tone-ink",
  indigo: "surface-tone-indigo",
  plum: "surface-tone-plum",
  celadon: "surface-tone-celadon",
  ochre: "surface-tone-ochre",
  cinnabar: "surface-tone-cinnabar",
}

export function StatusPill({
  label,
  value,
  icon: Icon,
  tone = "ink",
  className,
}: {
  label: string
  value: string
  icon?: ComponentType<{ className?: string }>
  tone?: Tone
  className?: string
}) {
  return (
    <div
      className={cn(
        "flex min-h-10 items-center gap-2 rounded-lg border px-3.5 py-2 text-[0.78rem] font-medium tracking-normal",
        toneClasses[tone],
        className,
      )}
    >
      {Icon ? <Icon className="h-3.5 w-3.5" /> : null}
      <span className="flex items-center gap-1.5 text-current">
        <span>{label}</span>
        <span className="font-mono text-[0.74rem] opacity-80">{value}</span>
      </span>
    </div>
  )
}
