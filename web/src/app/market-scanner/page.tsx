import { redirect } from "next/navigation"

export default function MarketScannerPage() {
  redirect("/trading?tab=scanner")
}
