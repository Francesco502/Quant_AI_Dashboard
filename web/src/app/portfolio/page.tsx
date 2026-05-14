"use client"

import { useState } from "react"
import { PersonalAssetsPanel } from "@/components/portfolio/PersonalAssetsPanel"
import { PortfolioRiskPanel } from "@/components/portfolio/PortfolioRiskPanel"
import { cn } from "@/lib/utils"

export default function PortfolioPage() {
  const [tab, setTab] = useState<"assets" | "risk">("assets")

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-1 rounded-full bg-muted/40 p-1 w-fit">
        {[
          { key: "assets", label: "个人资产" },
          { key: "risk", label: "风险分析" },
        ].map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setTab(key as "assets" | "risk")}
            className={cn(
              "rounded-full px-5 py-2 text-sm font-medium transition-all",
              tab === key
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "assets" ? <PersonalAssetsPanel /> : <PortfolioRiskPanel />}
    </div>
  )
}
