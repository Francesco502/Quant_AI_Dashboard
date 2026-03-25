import type { LucideIcon } from "lucide-react"
import {
  Activity,
  Bot,
  ChartColumn,
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
    description: "回到案头总览，先看今日重点、账户状态与主工作流入口。",
    defaultHref: "/",
    icon: Compass,
    tone: "indigo",
    items: [
      {
        name: "总览",
        href: "/",
        description: "查看全局概览、关键提醒与下一步入口。",
        icon: Compass,
      },
    ],
  },
  {
    id: "research",
    name: "研究",
    description: "集中查看市场、扫描、预测与决策支持内容。",
    defaultHref: "/market",
    icon: Bot,
    tone: "plum",
    items: [
      {
        name: "AI分析",
        href: "/market",
        description: "查看趋势、技术指标与风险拆解。",
        icon: LineChart,
      },
      {
        name: "大盘复盘",
        href: "/market-review",
        description: "回看市场结构、领涨领跌与情绪变化。",
        icon: ChartColumn,
      },
      {
        name: "市场扫描",
        href: "/market-scanner",
        description: "筛选值得继续跟踪的标的。",
        icon: ScanSearch,
      },
      {
        name: "预测研究",
        href: "/predictions",
        description: "查看历史、预测路径与误差分析。",
        icon: Radar,
      },
      {
        name: "决策仪表盘",
        href: "/dashboard-llm",
        description: "按模型、接口与标的生成辅助判断。",
        icon: Bot,
      },
      {
        name: "代理研究",
        href: "/agent-research",
        description: "查看代理研究流程、研究记录与输出。",
        icon: Bot,
      },
    ],
  },
  {
    id: "execution",
    name: "执行",
    description: "把策略、回测与模拟交易组织成一条执行闭环。",
    defaultHref: "/trading",
    icon: Activity,
    tone: "ochre",
    items: [
      {
        name: "模拟交易",
        href: "/trading",
        description: "查看账户、自动交易、订单与成交。",
        icon: Activity,
      },
      {
        name: "策略回测",
        href: "/backtest",
        description: "验证策略表现、参数与回撤情况。",
        icon: History,
      },
      {
        name: "量化策略",
        href: "/strategies",
        description: "浏览、运行与沉淀常用策略。",
        icon: LineChart,
      },
    ],
  },
  {
    id: "assets",
    name: "资产",
    description: "管理个人持仓、资产池与组合分析。",
    defaultHref: "/portfolio",
    icon: WalletCards,
    tone: "celadon",
    items: [
      {
        name: "个人资产",
        href: "/portfolio",
        description: "维护持仓、定投与区间收益。",
        icon: WalletCards,
      },
      {
        name: "组合分析",
        href: "/portfolio-analysis",
        description: "查看组合收益贡献、相关性与风险暴露。",
        icon: Radar,
      },
      {
        name: "组合回测",
        href: "/portfolio-backtest",
        description: "验证组合构建方案的历史表现。",
        icon: History,
      },
    ],
  },
]

const SYSTEM_ITEMS: WorkspaceItem[] = [
  {
    name: "系统监控",
    href: "/system-monitor",
    description: "查看服务状态、任务执行与告警记录。",
    icon: ShieldCheck,
  },
  {
    name: "系统设置",
    href: "/settings",
    description: "配置数据源、模型与全局行为。",
    icon: Settings2,
  },
]

export function getWorkspaceGroups(isAdmin: boolean): WorkspaceGroup[] {
  return [
    ...BASE_GROUPS,
    {
      id: "system",
      name: "系统",
    description: "维护环境配置、监控状态与系统权限。",
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
  const matched = groups.find((group) =>
    group.items.some((item) => isWorkspaceItemActive(pathname, item.href)),
  )

  return matched ?? groups[0]
}
