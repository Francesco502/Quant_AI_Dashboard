export type DateInput = Date | number | string | null | undefined

export const DEFAULT_LOCALE = "zh-CN"
export const DEFAULT_TIME_ZONE = "Asia/Shanghai"

const DATE_ONLY_RE = /^\d{4}-\d{2}-\d{2}$/
const LOCAL_DATE_TIME_RE = /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,3})?)?$/

function createFormatter(options: Intl.DateTimeFormatOptions) {
  return new Intl.DateTimeFormat(DEFAULT_LOCALE, {
    timeZone: DEFAULT_TIME_ZONE,
    ...options,
  })
}

const beijingDateFormatter = createFormatter({
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
})

export function toBeijingDate(value: DateInput) {
  if (value == null || value === "") return null

  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value
  }

  if (typeof value === "number") {
    const date = new Date(value)
    return Number.isNaN(date.getTime()) ? null : date
  }

  const raw = String(value).trim()
  if (!raw) return null

  const normalized = DATE_ONLY_RE.test(raw)
    ? `${raw}T00:00:00+08:00`
    : LOCAL_DATE_TIME_RE.test(raw)
      ? `${raw.replace(" ", "T")}+08:00`
      : raw

  const date = new Date(normalized)
  return Number.isNaN(date.getTime()) ? null : date
}

function fallbackText(value: DateInput, emptyText: string) {
  if (typeof value === "string" && value.trim()) {
    return value
  }
  return emptyText
}

function getCalendarParts(date: Date) {
  const parts = beijingDateFormatter.formatToParts(date)
  const year = parts.find((part) => part.type === "year")?.value ?? "0000"
  const month = parts.find((part) => part.type === "month")?.value ?? "01"
  const day = parts.find((part) => part.type === "day")?.value ?? "01"
  return { year, month, day }
}

function dayStamp(calendarKey: string) {
  const [year, month, day] = calendarKey.split("-").map(Number)
  return Date.UTC(year, month - 1, day) / 86400000
}

export function formatDateTimeInBeijing(
  value: DateInput,
  options: Intl.DateTimeFormatOptions = {},
  emptyText = "暂无",
) {
  const date = toBeijingDate(value)
  if (!date) return fallbackText(value, emptyText)

  return createFormatter({
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    ...options,
  }).format(date)
}

export function formatDateInBeijing(
  value: DateInput,
  options: Intl.DateTimeFormatOptions = {},
  emptyText = "暂无",
) {
  const date = toBeijingDate(value)
  if (!date) return fallbackText(value, emptyText)

  return createFormatter({
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    ...options,
  }).format(date)
}

export function formatMonthDayInBeijing(value: DateInput, emptyText = "暂无") {
  return formatDateInBeijing(
    value,
    {
      month: "2-digit",
      day: "2-digit",
    },
    emptyText,
  )
}

export function formatTimeInBeijing(
  value: DateInput,
  options: Intl.DateTimeFormatOptions = {},
  emptyText = "暂无",
) {
  const date = toBeijingDate(value)
  if (!date) return fallbackText(value, emptyText)

  return createFormatter({
    hour: "2-digit",
    minute: "2-digit",
    second: undefined,
    hour12: false,
    ...options,
  }).format(date)
}

export function getBeijingCalendarKey(value: DateInput) {
  const date = toBeijingDate(value)
  if (!date) return null
  const { year, month, day } = getCalendarParts(date)
  return `${year}-${month}-${day}`
}

export function getTodayInBeijing(referenceDate: DateInput = new Date()) {
  return getBeijingCalendarKey(referenceDate) ?? ""
}

export function diffBeijingCalendarDays(later: DateInput, earlier: DateInput) {
  const laterKey = getBeijingCalendarKey(later)
  const earlierKey = getBeijingCalendarKey(earlier)
  if (!laterKey || !earlierKey) return null
  return dayStamp(laterKey) - dayStamp(earlierKey)
}
