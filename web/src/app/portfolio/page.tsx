"use client"

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { AssetPoolPanel } from "@/components/portfolio/AssetPoolPanel"
import { PersonalAssetsPanel } from "@/components/portfolio/PersonalAssetsPanel"


export default function PortfolioPage() {
  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-[-0.02em] text-foreground/90">资产与持仓</h1>
        <p className="text-muted-foreground">
          把策略研究用的资产池和你自己的个人资产账本分开管理。
        </p>
      </div>

      <Tabs defaultValue="personal" className="space-y-3">
        <TabsList>
          <TabsTrigger value="personal">个人资产</TabsTrigger>
          <TabsTrigger value="pool">资产池</TabsTrigger>
        </TabsList>
        <TabsContent value="personal">
          <PersonalAssetsPanel />
        </TabsContent>
        <TabsContent value="pool">
          <AssetPoolPanel />
        </TabsContent>
      </Tabs>
    </div>
  )
}
