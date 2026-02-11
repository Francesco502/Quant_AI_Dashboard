"use client"

import React, { createContext, useContext, useState, useEffect } from "react"
import { api, DataSourceResponse } from "./api"

interface SettingsContextType {
  dataSources: string[]
  setDataSources: (sources: string[]) => void
  apiKeys: Record<string, string>
  setApiKeys: (keys: Record<string, string>) => void
  isLoading: boolean
}

const SettingsContext = createContext<SettingsContextType | undefined>(undefined)

export function SettingsProvider({ children }: { children: React.ReactNode }) {
  const [dataSources, setDataSourcesState] = useState<string[]>([])
  const [apiKeys, setApiKeysState] = useState<Record<string, string>>({})
  const [isLoading, setIsLoading] = useState(true)

  // Load from API on mount
  useEffect(() => {
    api.stz.getDataSources()
      .then((res) => {
        setDataSourcesState(res.sources || ["AkShare", "Binance"])
        setApiKeysState(res.api_keys || {})
      })
      .catch((err) => {
        console.error("Failed to load data sources:", err)
        setDataSourcesState(["AkShare", "Binance"])
      })
      .finally(() => setIsLoading(false))
  }, [])

  // Save to API when changed
  const updateDataSources = (newSources: string[]) => {
    setDataSourcesState(newSources)
    api.stz.updateDataSources(newSources, apiKeys).catch(console.error)
  }

  const updateApiKeys = (newKeys: Record<string, string>) => {
    setApiKeysState(newKeys)
    api.stz.updateDataSources(dataSources, newKeys).catch(console.error)
  }

  return (
    <SettingsContext.Provider
      value={{
        dataSources,
        setDataSources: updateDataSources,
        apiKeys,
        setApiKeys: updateApiKeys,
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
