import { redirect } from "next/navigation"

export default function PortfolioBacktestPage() {
  redirect("/backtest?tab=portfolio")
}
