import { redirect } from "next/navigation"

export default function BacktestOptimizerPage() {
  redirect("/backtest?tab=optimize")
}
