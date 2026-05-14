"use client"

import { createContext, useCallback, useContext, useEffect, useState } from "react"

type Theme = "light" | "dark"

type ThemeContextValue = {
  theme: Theme
  toggleTheme: () => void
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

function getSystemTheme(): Theme {
  if (typeof window === "undefined") return "light"
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
}

function getStoredTheme(): Theme | null {
  if (typeof window === "undefined") return null
  try {
    const stored = localStorage.getItem("theme")
    if (stored === "dark" || stored === "light") return stored
  } catch {
    // localStorage unavailable
  }
  return null
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() => getStoredTheme() ?? getSystemTheme())

  useEffect(() => {
    const root = document.documentElement
    if (theme === "dark") {
      root.classList.add("dark")
    } else {
      root.classList.remove("dark")
    }
    try {
      localStorage.setItem("theme", theme)
    } catch {
      // ignore
    }
  }, [theme])

  // Listen for system theme changes when no stored preference
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)")
    const handler = (e: MediaQueryListEvent) => {
      const stored = getStoredTheme()
      if (!stored) {
        setTheme(e.matches ? "dark" : "light")
      }
    }
    mq.addEventListener("change", handler)
    return () => mq.removeEventListener("change", handler)
  }, [])

  const toggleTheme = useCallback(() => {
    setTheme((prev) => (prev === "light" ? "dark" : "light"))
  }, [])

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) {
    return { theme: "light" as Theme, toggleTheme: () => {} }
  }
  return ctx
}
