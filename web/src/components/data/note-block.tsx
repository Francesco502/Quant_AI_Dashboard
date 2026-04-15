import { type ReactNode } from "react"

import { SONG_COLORS } from "@/lib/chart-theme"
import { cn } from "@/lib/utils"

type NoteTone = "default" | "accent" | "positive" | "negative"

function resolveTone(tone: NoteTone) {
  if (tone === "accent") {
    return {
      borderColor: "rgba(111,124,142,0.14)",
      backgroundColor: "rgba(111,124,142,0.07)",
      color: SONG_COLORS.indigo,
    }
  }
  if (tone === "positive") {
    return {
      borderColor: "rgba(77,115,88,0.16)",
      backgroundColor: "rgba(77,115,88,0.07)",
      color: SONG_COLORS.positive,
    }
  }
  if (tone === "negative") {
    return {
      borderColor: "rgba(182,69,60,0.16)",
      backgroundColor: "rgba(182,69,60,0.07)",
      color: SONG_COLORS.negative,
    }
  }
  return undefined
}

export function NoteBlock({
  title,
  children,
  icon,
  tone = "default",
  muted = false,
  className,
}: {
  title?: ReactNode
  children: ReactNode
  icon?: ReactNode
  tone?: NoteTone
  muted?: boolean
  className?: string
}) {
  const toneStyle = resolveTone(tone)

  return (
    <div
      className={cn("data-note text-sm leading-7 text-muted-foreground", muted && "data-note-muted", className)}
      style={toneStyle}
    >
      {title ? (
        <div className="mb-2 flex items-center gap-2 text-sm font-medium text-foreground/85">
          {icon}
          <span>{title}</span>
        </div>
      ) : null}
      <div>{children}</div>
    </div>
  )
}
