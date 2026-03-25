import type { ForecastResult, PricePoint } from "@/lib/api"

export type ForecastChartRow = {
  date: string
  label: string
  historyPrice: number | null
  forecastPrice: number | null
}

export type ForecastSummary = {
  current: number
  target: number
  pct: number
  up: boolean
}

export type ErrorInsight = {
  key: string
  label: string
  hint: string
  valueText: string
  description: string
  interpretation: string
}

function metricValue(metrics: ForecastResult["metrics"] | undefined, keys: string[]) {
  if (!metrics) return null
  for (const key of keys) {
    const value = metrics[key as keyof typeof metrics]
    if (typeof value === "number" && Number.isFinite(value)) return value
  }
  return null
}

export function formatPrice(value: number) {
  return Number(value).toFixed(2)
}

export function shortDate(date: string) {
  return new Date(date).toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" })
}

export function buildForecastRows(history: PricePoint[], forecast: PricePoint[]): ForecastChartRow[] {
  return [
    ...history.map((point) => ({
      date: point.date,
      label: shortDate(point.date),
      historyPrice: point.price,
      forecastPrice: null,
    })),
    ...forecast.map((point) => ({
      date: point.date,
      label: shortDate(point.date),
      historyPrice: null,
      forecastPrice: point.price,
    })),
  ]
}

export function getYAxisDomain(values: number[]) {
  if (values.length === 0) return ["auto", "auto"] as const
  const min = Math.min(...values)
  const max = Math.max(...values)
  const padding = Math.max((max - min) * 0.12, max * 0.02, 0.01)
  return [Number((min - padding).toFixed(4)), Number((max + padding).toFixed(4))] as const
}

export function getForecastSummary(history: PricePoint[], predictions: PricePoint[]) {
  if (!history.length || !predictions.length) return null
  const current = history.at(-1)?.price ?? 0
  const target = predictions.at(-1)?.price ?? current
  const pct = (target - current) / Math.max(current, 1e-6)
  return { current, target, pct, up: pct >= 0 } satisfies ForecastSummary
}

export function buildErrorInsights(
  metrics: ForecastResult["metrics"] | undefined,
  latestPrice: number | null
): ErrorInsight[] {
  const mae = metricValue(metrics, ["MAE", "mae"])
  const rmse = metricValue(metrics, ["RMSE", "rmse"])
  const mape = metricValue(metrics, ["MAPE", "mape"])
  const nrmse = rmse != null && latestPrice != null ? rmse / Math.max(latestPrice, 1e-6) : null

  const maeRatio = mae != null && latestPrice != null ? mae / Math.max(latestPrice, 1e-6) : null

  const describeRelative = (ratio: number | null, mild: number, medium: number) => {
    if (ratio == null) return "接口未返回足够数据，当前无法判断。"
    if (ratio <= mild) return "误差落在较低区间，短周期参考价值较高。"
    if (ratio <= medium) return "误差处于可用区间，适合配合趋势判断而非单点绝对定价。"
    return "误差偏大，应把预测更多当作方向参考，而不是精确定价。"
  }

  return [
    {
      key: "mape",
      label: "MAPE",
      hint: "平均绝对百分比误差，用百分比衡量预测值与真实值平均偏差，便于跨标的横向比较。",
      valueText: mape != null ? `${mape.toFixed(2)}%` : "--",
      description: "相对误差，越低越稳。",
      interpretation:
        mape == null
          ? "当前模型没有返回 MAPE。"
          : mape <= 3
            ? "相对误差较低，适合做短周期节奏判断。"
            : mape <= 8
              ? "相对误差可接受，建议结合量价和趋势共同使用。"
              : "相对误差偏大，更适合看方向，不适合看精确目标位。",
    },
    {
      key: "mae",
      label: "MAE",
      hint: "平均绝对误差，表示预测结果平均偏离实际价格多少个价格单位。",
      valueText: mae != null ? formatPrice(mae) : "--",
      description: "绝对误差，越低越好。",
      interpretation: describeRelative(maeRatio, 0.01, 0.03),
    },
    {
      key: "rmse",
      label: "RMSE",
      hint: "均方根误差，会放大大偏差样本，适合用来识别模型是否容易出现明显失真。",
      valueText: rmse != null ? formatPrice(rmse) : "--",
      description: "大偏差越多，RMSE 越高。",
      interpretation: describeRelative(nrmse, 0.015, 0.04),
    },
    {
      key: "nrmse",
      label: "NRMSE",
      hint: "把 RMSE 再除以当前价格，便于判断误差相对于价格本身的比例。",
      valueText: nrmse != null ? `${(nrmse * 100).toFixed(2)}%` : "--",
      description: "标准化误差，适合快速判定可用性。",
      interpretation:
        nrmse == null
          ? "缺少 RMSE 或最新价格，无法计算。"
          : nrmse <= 0.015
            ? "大偏差控制得较好，预测曲线稳定性较强。"
            : nrmse <= 0.04
              ? "仍可用于方向判断，但不宜把拐点当作确定信号。"
              : "说明极端误差偏高，建议降低单次预测权重。",
    },
  ]
}

export function summarizeError(insights: ErrorInsight[]) {
  const mapeText = insights.find((item) => item.key === "mape")?.valueText
  const nrmseText = insights.find((item) => item.key === "nrmse")?.valueText
  const mapeValue = insights.find((item) => item.key === "mape")?.valueText

  if (mapeValue === "--" && nrmseText === "--") {
    return {
      title: "缺少误差回传",
      description: "当前模型只返回预测路径，没有附带完整回测误差，建议把本次结果用于方向观察。",
    }
  }

  const first = insights.find((item) => item.key === "mape" && item.valueText !== "--")
  if (first?.valueText && first.valueText !== "--") {
    const value = Number(first.valueText.replace("%", ""))
    if (Number.isFinite(value)) {
      if (value <= 3) {
        return {
          title: "综合误差偏低",
          description: `MAPE 为 ${mapeText}，短周期参考价值较好，但仍需配合趋势和成交量使用。`,
        }
      }
      if (value <= 8) {
        return {
          title: "综合误差可用",
          description: `MAPE 为 ${mapeText}，适合看方向与节奏，不宜把目标价当作精确点位。`,
        }
      }
    }
  }

  return {
    title: "综合误差偏高",
    description: `当前误差控制一般${nrmseText && nrmseText !== "--" ? `，NRMSE 为 ${nrmseText}` : ""}，建议降低对单次预测结果的依赖。`,
  }
}
