"use client"

import { ThemeProvider } from "@/lib/theme-context"
import { SettingsProvider } from "@/lib/settings-context"
import { AuthProvider } from "@/lib/auth-context"

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <SettingsProvider>
        <ThemeProvider>
          {children}
        </ThemeProvider>
      </SettingsProvider>
    </AuthProvider>
  )
}
