export type StrategyParameterHint = {
  name: string
  defaultValue: string
  range: string
  note: string
}

export type StrategyDescriptor = {
  id: string
  title: string
  family: string
  summary: string
  principle: string
  suitableFor: string[]
  strengths: string[]
  risks: string[]
  watchpoints: string[]
  parameters: StrategyParameterHint[]
  matchers: string[]
}

export const STRATEGY_LIBRARY: StrategyDescriptor[] = [
  {
    id: "bbi-kdj",
    title: "BBI-KDJ 低位布局",
    family: "低位回升",
    summary: "用 BBI 位置和 KDJ 低位信号寻找回撤后的修复机会，适合做日线级别的低位埋伏。",
    principle: "先确认价格仍围绕中期均衡区，再用 KDJ 的低位钝化或拐点判断短线修复是否开始。",
    suitableFor: ["震荡下沿", "阶段性超跌反弹", "中短线观察池"],
    strengths: ["逻辑直观，适合日线复盘", "能过滤掉一部分高位追涨", "适合和量能、均线共振一起使用"],
    risks: ["弱势下跌趋势里容易反复抄底失败", "KDJ 指标本身会提前钝化", "需要控制仓位，避免单点重仓"],
    watchpoints: ["优先看量价是否同步修复", "跌破中期均衡区时不宜机械补仓", "最好配合行业或指数环境过滤"],
    parameters: [
      { name: "J 阈值", defaultValue: "15", range: "10-20", note: "越低越强调极端超卖位置" },
      { name: "BBI 分位阈值", defaultValue: "0.20", range: "0.10-0.35", note: "用于限定价格与均衡区的距离" },
    ],
    matchers: ["bbikdjselector", "bbi-kdj", "bbi kdj", "灏戝鎴樻硶", "少妇战法", "bbikdj"],
  },
  {
    id: "superb1",
    title: "SuperB1 趋势突破",
    family: "趋势强化",
    summary: "在基础低位信号之上，再加入近期强势与放量确认，用于寻找加速前的趋势突破点。",
    principle: "先出现 B1 类低位启动迹象，再用近端价格结构、放量和回撤控制确认趋势已经转强。",
    suitableFor: ["主升启动前", "强势股回踩再起", "波段进攻型筛选"],
    strengths: ["比单纯低位抄底更强调确认", "能筛出更强的相对趋势", "适合与交易计划联动"],
    risks: ["突破后回踩失败会带来快速回撤", "强势品种容易出现拥挤交易", "追价过高会压缩盈亏比"],
    watchpoints: ["最好结合板块强弱判断", "放量但涨幅过大时要警惕隔日回吐", "更适合做候选池，不宜盲目满仓追击"],
    parameters: [
      { name: "观察窗口", defaultValue: "10", range: "5-20", note: "越短越敏感，越长越稳健" },
      { name: "量能倍数", defaultValue: "1.8x", range: "1.2x-2.5x", note: "用于确认突破是否具备资金配合" },
    ],
    matchers: ["superb1selector", "superb1", "super b1", "superb1鎴樻硶", "superb1战法"],
  },
  {
    id: "bbi-short-long",
    title: "BBI 长短波段",
    family: "均衡转强",
    summary: "用 BBI 上行趋势叠加短长周期摆动指标，寻找中枢转强后的顺势切入点。",
    principle: "先要求中期均衡线抬升，再观察短长周期动量是否同时回到偏强区间，避免只靠单一指标入场。",
    suitableFor: ["趋势初段", "中枢抬升行情", "多因子确认型波段"],
    strengths: ["比单指标更稳健", "适合做候选池分层", "便于和仓位管理结合"],
    risks: ["条件较多，信号频率偏低", "趋势末端会有滞后", "参数不当时容易错过启动初期"],
    watchpoints: ["适合放在第二层筛选，而不是第一层广撒网", "如果 BBI 斜率转弱，应及时降权", "长短周期冲突时以风险控制优先"],
    parameters: [
      { name: "短周期", defaultValue: "5", range: "3-10", note: "控制短线摆动敏感度" },
      { name: "长周期", defaultValue: "21", range: "13-34", note: "用于判断波段强弱结构" },
    ],
    matchers: ["bbishortlongselector", "bbi short long", "bbi长短", "琛ョエ鎴樻硶", "补票战法"],
  },
  {
    id: "peak-kdj",
    title: "Peak KDJ 回踩确认",
    family: "峰谷回踩",
    summary: "围绕前期峰谷结构与 KDJ 位置做确认，适合捕捉强势调整后的二次起点。",
    principle: "价格先形成可识别的结构，再用 KDJ 的低位回踩确认调整是否接近结束。",
    suitableFor: ["强势股二次上车", "结构化回踩", "有明确支撑位的波段标的"],
    strengths: ["更重视结构，不完全依赖均线", "适合做强势品种二次筛选", "回撤定义相对清晰"],
    risks: ["结构判断受样本窗口影响较大", "高波动个股容易出现假支撑", "需要止损纪律"],
    watchpoints: ["优先关注前高附近的承接", "极端波动日不宜只看单日 KDJ", "没有量能配合时，回踩成功率会下降"],
    parameters: [
      { name: "峰谷回看", defaultValue: "120", range: "60-180", note: "用于识别关键结构区间" },
      { name: "波动阈值", defaultValue: "3%", range: "2%-6%", note: "用于过滤过度噪音" },
    ],
    matchers: ["peakkdjselector", "peak kdj", "peakkdj", "濉潙鎴樻硶", "填坑战法"],
  },
  {
    id: "ma60-volume-wave",
    title: "MA60 放量上穿",
    family: "均线突破",
    summary: "关注价格重新站上 MA60 且伴随量能放大，用于寻找中期趋势恢复的拐点。",
    principle: "MA60 作为中期分界线，价格回到其上且成交活跃，往往意味着资金重新认可趋势方向。",
    suitableFor: ["中期反转", "平台突破", "趋势恢复确认"],
    strengths: ["规则明确，易于执行", "适合配合指数环境过滤", "结果便于复盘统计"],
    risks: ["假突破会导致追高回撤", "量能异常放大后也可能是分歧顶", "横盘市场里信号质量下降"],
    watchpoints: ["突破当天不宜只看收盘价，还要看量能结构", "MA60 斜率向下时要降低预期", "适合与板块热度一起评估"],
    parameters: [
      { name: "回看窗口", defaultValue: "25", range: "15-40", note: "用于寻找最近一次有效上穿" },
      { name: "放量倍数", defaultValue: "1.8x", range: "1.3x-2.5x", note: "量能确认阈值" },
    ],
    matchers: ["ma60crossvolumewaveselector", "ma60", "ma60 cross", "volume wave", "涓婄┛60鏀鹃噺鎴樻硶", "上穿60放量战法"],
  },
]

function normalizeMatcher(value: string) {
  return value.trim().toLowerCase()
}

export function resolveStrategyDescriptor(value?: string | null) {
  if (!value) return null
  const normalized = normalizeMatcher(value)
  const resolveCandidates = (item: StrategyDescriptor) => [item.title, item.family, ...item.matchers]
  return (
    STRATEGY_LIBRARY.find((item) => resolveCandidates(item).some((matcher) => normalizeMatcher(matcher) === normalized)) ??
    STRATEGY_LIBRARY.find((item) => resolveCandidates(item).some((matcher) => normalized.includes(normalizeMatcher(matcher)))) ??
    null
  )
}

export function getStrategyDisplayName(value?: string | null) {
  const descriptor = resolveStrategyDescriptor(value)
  if (descriptor) return descriptor.title
  return value?.trim() || "未命名策略"
}
