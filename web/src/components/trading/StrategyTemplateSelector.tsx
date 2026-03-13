"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { motion } from "framer-motion"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { api, type StrategyTemplate } from "@/lib/api"
import { ChevronDown, FileText, FolderOpen, Heart, Save, Sparkles, Star, Trash2 } from "lucide-react"
import { toast } from "sonner"

interface StrategyTemplateSelectorProps {
  currentStrategyId: string
  currentStrategyType: "classic" | "stz"
  currentParams: Record<string, unknown>
  onLoadTemplate: (template: { params: Record<string, unknown>; name: string }) => void
}

const PRESET_TEMPLATES: Array<Partial<StrategyTemplate>> = [
  {
    id: -1,
    template_name: "稳健长期（Conservative Long-Term）",
    strategy_id: "sma_crossover",
    strategy_type: "classic",
    description: "适合趋势跟随、换手率较低的参数组合。",
    params: { short_window: 20, long_window: 60 },
    is_favorite: false,
    is_public: true,
    created_at: "",
    updated_at: "",
  },
  {
    id: -2,
    template_name: "激进短线（Aggressive Short-Term）",
    strategy_id: "sma_crossover",
    strategy_type: "classic",
    description: "更敏感地捕捉短期波动。",
    params: { short_window: 5, long_window: 15 },
    is_favorite: false,
    is_public: true,
    created_at: "",
    updated_at: "",
  },
  {
    id: -3,
    template_name: "均值回归标准（Mean Reversion）",
    strategy_id: "mean_reversion",
    strategy_type: "classic",
    description: "基于布林带的均值回归基础参数。",
    params: { window: 20, std_dev: 2.0 },
    is_favorite: false,
    is_public: true,
    created_at: "",
    updated_at: "",
  },
]

export function StrategyTemplateSelector({
  currentStrategyId,
  currentStrategyType,
  currentParams,
  onLoadTemplate,
}: StrategyTemplateSelectorProps) {
  const [templates, setTemplates] = useState<StrategyTemplate[]>([])
  const [saving, setSaving] = useState(false)
  const [showSaveDialog, setShowSaveDialog] = useState(false)
  const [templateName, setTemplateName] = useState("")
  const [templateDesc, setTemplateDesc] = useState("")
  const [selectedTemplate, setSelectedTemplate] = useState<StrategyTemplate | null>(null)

  const fetchTemplates = useCallback(async () => {
    try {
      const response = await api.backtest.templates.list({ strategy_type: currentStrategyType })
      setTemplates(response ?? [])
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : ""
      if (message.includes("Endpoint not found")) {
        setTemplates([])
        return
      }
      console.error("Failed to load templates:", error)
    }
  }, [currentStrategyType])

  useEffect(() => {
    void fetchTemplates()
  }, [fetchTemplates, currentStrategyId])

  const handleSaveTemplate = useCallback(async () => {
    if (!templateName.trim()) {
      toast.error("模板名称不能为空")
      return
    }

    setSaving(true)
    try {
      await api.backtest.templates.create({
        template_name: templateName,
        strategy_id: currentStrategyId,
        strategy_type: currentStrategyType,
        description: templateDesc,
        params: currentParams,
        is_public: false,
      })

      toast.success("模板已保存")
      setShowSaveDialog(false)
      setTemplateName("")
      setTemplateDesc("")
      await fetchTemplates()
    } catch (error: unknown) {
      console.error("Failed to save template:", error)
      toast.error("保存模板失败")
    } finally {
      setSaving(false)
    }
  }, [templateName, currentStrategyId, currentStrategyType, templateDesc, currentParams, fetchTemplates])

  const handleDeleteTemplate = useCallback(
    async (id: number) => {
      if (!window.confirm("Delete this template?")) {
        return
      }

      try {
        await api.backtest.templates.delete(id)
        toast.success("模板已删除")
        await fetchTemplates()
      } catch (error: unknown) {
        console.error("Failed to delete template:", error)
        toast.error("删除模板失败")
      }
    },
    [fetchTemplates]
  )

  const handleToggleFavorite = useCallback(
    async (template: StrategyTemplate) => {
      try {
        await api.backtest.templates.update(template.id, {
          is_favorite: !template.is_favorite,
        })
        await fetchTemplates()
        toast.success(template.is_favorite ? "已取消收藏" : "已加入收藏")
      } catch (error: unknown) {
        console.error("Failed to update template:", error)
        toast.error("更新模板失败")
      }
    },
    [fetchTemplates]
  )

  const handleLoadTemplate = useCallback(
    (template: Partial<StrategyTemplate>) => {
      if (!template.params || !template.template_name) {
        return
      }

      if (
        typeof template.id === "number" &&
        typeof template.strategy_id === "string" &&
        typeof template.strategy_type === "string"
      ) {
        setSelectedTemplate(template as StrategyTemplate)
      }

      onLoadTemplate({ params: template.params as Record<string, unknown>, name: template.template_name })
      toast.success(`已加载模板：${template.template_name}`)
    },
    [onLoadTemplate]
  )

  const relevantPresets = useMemo(
    () => PRESET_TEMPLATES.filter((template) => template.strategy_id === currentStrategyId),
    [currentStrategyId]
  )
  const relevantUserTemplates = useMemo(
    () => templates.filter((template) => template.strategy_id === currentStrategyId),
    [templates, currentStrategyId]
  )
  const favoriteTemplates = useMemo(
    () => relevantUserTemplates.filter((template) => template.is_favorite),
    [relevantUserTemplates]
  )
  const regularTemplates = useMemo(
    () => relevantUserTemplates.filter((template) => !template.is_favorite),
    [relevantUserTemplates]
  )

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <Label className="text-xs font-medium uppercase tracking-wider text-foreground/40">策略模板（Templates）</Label>
        <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => setShowSaveDialog(true)}>
          <Save className="mr-1 h-3.5 w-3.5" />
          保存当前参数
        </Button>
      </div>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="outline"
            className="h-9 w-full justify-between"
            disabled={relevantPresets.length === 0 && relevantUserTemplates.length === 0}
          >
            <span className="flex items-center gap-2">
              <FolderOpen className="h-4 w-4 text-muted-foreground" />
              {selectedTemplate ? selectedTemplate.template_name : "选择模板"}
            </span>
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent className="w-80">
          {relevantPresets.length > 0 && (
            <>
              <DropdownMenuLabel className="flex items-center gap-2">
                <Sparkles className="h-3.5 w-3.5 text-yellow-500" />
                预设模板
              </DropdownMenuLabel>
              {relevantPresets.map((template) => (
                <DropdownMenuItem key={template.id} onClick={() => handleLoadTemplate(template)} className="cursor-pointer">
                  <div className="flex flex-col">
                    <span className="font-medium">{template.template_name}</span>
                    <span className="text-xs text-muted-foreground">{template.description}</span>
                  </div>
                </DropdownMenuItem>
              ))}
              <DropdownMenuSeparator />
            </>
          )}

          {favoriteTemplates.length > 0 && (
            <>
              <DropdownMenuLabel className="flex items-center gap-2">
                <Star className="h-3.5 w-3.5 fill-yellow-400 text-yellow-400" />
                收藏
              </DropdownMenuLabel>
              {favoriteTemplates.map((template) => (
                <DropdownMenuItem
                  key={template.id}
                  className="group flex cursor-pointer items-center justify-between"
                  onClick={() => handleLoadTemplate(template)}
                >
                  <span>{template.template_name}</span>
                  <div className="flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                    <button
                      onClick={(event) => {
                        event.stopPropagation()
                        void handleToggleFavorite(template)
                      }}
                      className="rounded p-1 hover:bg-muted"
                    >
                      <Heart className="h-3 w-3 fill-current" />
                    </button>
                    <button
                      onClick={(event) => {
                        event.stopPropagation()
                        void handleDeleteTemplate(template.id)
                      }}
                      className="rounded p-1 text-red-500 hover:bg-red-100"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </div>
                </DropdownMenuItem>
              ))}
              <DropdownMenuSeparator />
            </>
          )}

          {regularTemplates.length > 0 && (
            <>
              <DropdownMenuLabel className="flex items-center gap-2">
                <FileText className="h-3.5 w-3.5" />
                我的模板（{regularTemplates.length}）
              </DropdownMenuLabel>
              {regularTemplates.map((template) => (
                <DropdownMenuItem
                  key={template.id}
                  className="group flex cursor-pointer items-center justify-between"
                  onClick={() => handleLoadTemplate(template)}
                >
                  <span>{template.template_name}</span>
                  <div className="flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                    <button
                      onClick={(event) => {
                        event.stopPropagation()
                        void handleToggleFavorite(template)
                      }}
                      className="rounded p-1 hover:bg-muted"
                    >
                      <Star className="h-3 w-3" />
                    </button>
                    <button
                      onClick={(event) => {
                        event.stopPropagation()
                        void handleDeleteTemplate(template.id)
                      }}
                      className="rounded p-1 text-red-500 hover:bg-red-100"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </div>
                </DropdownMenuItem>
              ))}
            </>
          )}

          {relevantPresets.length === 0 && relevantUserTemplates.length === 0 && (
            <div className="px-2 py-3 text-center text-sm text-muted-foreground">暂无可用模板</div>
          )}
        </DropdownMenuContent>
      </DropdownMenu>

      {selectedTemplate && (
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="space-y-2 rounded-lg bg-muted/50 p-3 text-xs">
          <div className="flex items-center justify-between">
            <span className="font-medium">{selectedTemplate.template_name}</span>
            {selectedTemplate.is_favorite && <Star className="h-3.5 w-3.5 fill-yellow-400 text-yellow-400" />}
          </div>
          {selectedTemplate.description && <p className="text-muted-foreground">{selectedTemplate.description}</p>}
          <div className="flex flex-wrap gap-1">
            {Object.entries(selectedTemplate.params).slice(0, 3).map(([key, value]) => (
              <Badge key={key} variant="secondary" className="text-[10px]">
                {key}: {String(value).slice(0, 10)}
              </Badge>
            ))}
            {Object.keys(selectedTemplate.params).length > 3 && (
              <Badge variant="secondary" className="text-[10px]">
                +{Object.keys(selectedTemplate.params).length - 3}
              </Badge>
            )}
          </div>
        </motion.div>
      )}

      <Dialog open={showSaveDialog} onOpenChange={setShowSaveDialog}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>保存策略模板</DialogTitle>
            <DialogDescription>将当前参数保存为模板，便于快速复用。</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="template-name">模板名称</Label>
              <Input
                id="template-name"
                value={templateName}
                onChange={(event) => setTemplateName(event.target.value)}
                placeholder="例如：趋势跟随参数组"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="template-description">说明（可选）</Label>
              <Input
                id="template-description"
                value={templateDesc}
                onChange={(event) => setTemplateDesc(event.target.value)}
                placeholder="该模板适合什么场景？"
              />
            </div>
            <div className="rounded bg-muted p-2 text-xs text-muted-foreground">
              <div>策略：{currentStrategyId}</div>
              <div>类型：{currentStrategyType}</div>
              <div>参数数量：{Object.keys(currentParams).length}</div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowSaveDialog(false)}>
              取消
            </Button>
            <Button onClick={() => void handleSaveTemplate()} disabled={saving || !templateName.trim()}>
              {saving ? "保存中..." : "保存"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default StrategyTemplateSelector
