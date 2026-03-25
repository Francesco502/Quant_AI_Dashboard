"use client"

import React, { createContext, useContext, useState, useEffect } from "react"
import { api } from "./api"

interface SettingsContextType {
  dataSources: string[]
  apiKeyStatus: {
    Tushare: boolean
    AlphaVantage: boolean
  }
  configurationMode: "env_locked"
  isLoading: boolean
}

const SettingsContext = createContext<SettingsContextType | undefined>(undefined)

export function SettingsProvider({ children }: { children: React.ReactNode }) {
  const [dataSources, setDataSourcesState] = useState<string[]>(["Tushare", "AkShare"])
  const [apiKeyStatus, setApiKeyStatus] = useState<{ Tushare: boolean; AlphaVantage: boolean }>({
    Tushare: false,
    AlphaVantage: false,
  })
  const [configurationMode, setConfigurationMode] = useState<"env_locked">("env_locked")
  const [isLoading, setIsLoading] = useState(
    () => typeof window !== "undefined" && !!localStorage.getItem("token")
  )

  // Load from API on mount
  useEffect(() => {
    if (typeof window === "undefined" || !localStorage.getItem("token")) return

    api.stz.getDataSources()
      .then((res) => {
        setDataSourcesState(res.sources || ["Tushare", "AkShare"])
        setApiKeyStatus(res.api_key_status || { Tushare: false, AlphaVantage: false })
        setConfigurationMode(res.configuration_mode || "env_locked")
      })
      .catch(() => {
        setDataSourcesState(["Tushare", "AkShare"])
      })
      .finally(() => setIsLoading(false))
  }, [])

  return (
    <SettingsContext.Provider
      value={{
        dataSources,
        apiKeyStatus,
        configurationMode,
        isLoading
      }}
    >
      {children}
    </SettingsContext.Provider>
  )
}

export function useSettings() {
  const context = useContext(SettingsContext)
  if (context === undefined) {
    throw new Error("useSettings must be used within a SettingsProvider")
  }
  return context
}
