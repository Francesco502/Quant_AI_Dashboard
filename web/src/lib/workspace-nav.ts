import type { LucideIcon } from "lucide-react"
import {
  Activity,
  Bot,
  ChartColumn,
  ClipboardCheck,
  Compass,
  History,
  LineChart,
  Radar,
  ScanSearch,
  Settings2,
  ShieldCheck,
  Users,
  WalletCards,
} from "lucide-react"

export type WorkspaceItem = {
  name: string
  href: string
  description: string
  icon: LucideIcon
}

export type WorkspaceGroup = {
  id: "workbench" | "research" | "execution" | "assets" | "system"
  name: string
  description: string
  defaultHref: string
  icon: LucideIcon
  tone: "indigo" | "celadon" | "plum" | "ochre" | "ink"
  items: WorkspaceItem[]
}

const BASE_GROUPS: WorkspaceGroup[] = [
  {
    id: "workbench",
    name: "工作台",
    description: "查看总览、每日任务与关键复盘入口。",
    defaultHref: "/daily-workbench",
    icon: Compass,
    tone: "indigo",
    items: [
      {
        name: "日常决策",
        href: "/daily-workbench",
        description: "把市场复盘、数据新鲜度、扫描、回测和纸面账户合成每日入口。",
        icon: ClipboardCheck,
      },
      {
        name: "总览",
        href: "/",
        description: "查看全局概览、当前状态与常用操作入口。",
        icon: Compass,
      },
    ],
  },
  {
    id: "research",
    name: "研究",
    description: "集中处理市场观察、扫描、预测与模型研究。",
    defaultHref: "/market",
    icon: Bot,
    tone: "plum",
    items: [
      {
        name: "技术与风险",
        href: "/market",
        description: "查看技术指标、波动特征与风险拆解。",
        icon: LineChart,
      },
      {
        name: "大盘复盘",
        href: "/market-review",
        description: "回看市场广度、主线结构与情绪节奏。",
        icon: ChartColumn,
      },
      {
        name: "市场扫描",
        href: "/market-scanner",
        description: "筛选值得继续跟踪的候选标的。",
        icon: ScanSearch,
      },
      {
        name: "AI 预测研究",
        href: "/predictions",
        description: "查看历史走势、预测路径与误差评估。",
        icon: Radar,
      },
      {
        name: "LLM 研究工作台",
        href: "/dashboard-llm",
        description: "统一处理结构化决策与 Agent 研究。",
        icon: Bot,
      },
    ],
  },
  {
    id: "execution",
    name: "执行",
    description: "把回测、策略与模拟交易收拢到一条执行链路。",
    defaultHref: "/backtest",
    icon: Activity,
    tone: "ochre",
    items: [
      {
        name: "回测中心",
        href: "/backtest",
        description: "统一处理策略回测、组合回测、扫描与参数优化。",
        icon: History,
      },
      {
        name: "模拟交易",
        href: "/trading",
        description: "查看账户、订单、成交与自动纸面执行状态。",
        icon: Activity,
      },
      {
        name: "量化策略",
        href: "/strategies",
        description: "运行、学习并沉淀常用策略模板。",
        icon: LineChart,
      },
    ],
  },
  {
    id: "assets",
    name: "资产",
    description: "聚焦个人资产与资产池两类核心入口。",
    defaultHref: "/portfolio",
    icon: WalletCards,
    tone: "celadon",
    items: [
      {
        name: "个人资产",
        href: "/portfolio",
        description: "维护真实持仓、收益轨迹与账户视图。",
        icon: WalletCards,
      },
      {
        name: "资产池",
        href: "/asset-pool",
        description: "管理研究、扫描与回测共用的候选资产。",
        icon: Radar,
      },
    ],
  },
]

const SYSTEM_ITEMS: WorkspaceItem[] = [
  {
    name: "系统监控",
    href: "/system-monitor",
    description: "查看服务状态、资源指标与告警记录。",
    icon: ShieldCheck,
  },
  {
    name: "系统设置",
    href: "/settings",
    description: "配置数据源、模型服务、备份与全局行为。",
    icon: Settings2,
  },
]

const GROUP_PREFIXES: Record<WorkspaceGroup["id"], string[]> = {
  workbench: ["/", "/daily-workbench"],
  research: ["/market", "/market-review", "/market-scanner", "/predictions", "/dashboard-llm"],
  execution: ["/backtest", "/trading", "/strategies"],
  assets: ["/portfolio", "/asset-pool"],
  system: ["/settings", "/system-monitor", "/users"],
}

export function getWorkspaceGroups(isAdmin: boolean): WorkspaceGroup[] {
  return [
    ...BASE_GROUPS,
    {
      id: "system",
      name: "系统",
      description: "维护运行环境、配置状态与系统权限。",
      defaultHref: "/settings",
      icon: Settings2,
      tone: "ink",
      items: isAdmin
        ? [
            ...SYSTEM_ITEMS,
            {
              name: "用户管理",
              href: "/users",
              description: "管理账户角色与访问权限。",
              icon: Users,
            },
          ]
        : [...SYSTEM_ITEMS],
    },
  ]
}

export function isWorkspaceItemActive(pathname: string, href: string): boolean {
  if (href === "/") {
    return pathname === "/"
  }

  return pathname === href || pathname.startsWith(`${href}/`)
}

export function getActiveWorkspaceGroup(pathname: string, groups: WorkspaceGroup[]): WorkspaceGroup {
  const matchedByItem = groups.find((group) =>
    group.items.some((item) => isWorkspaceItemActive(pathname, item.href)),
  )
  if (matchedByItem) {
    return matchedByItem
  }

  const matchedByPrefix = groups.find((group) =>
    (GROUP_PREFIXES[group.id] ?? []).some((prefix) =>
      prefix === "/" ? pathname === "/" : pathname === prefix || pathname.startsWith(`${prefix}/`),
    ),
  )

  return matchedByPrefix ?? groups[0]
}
