"use client"

import { Component, type ReactNode } from "react"
import { AlertTriangle, RefreshCw } from "lucide-react"

interface ErrorBoundaryProps {
  children: ReactNode
  fallback?: ReactNode
}

interface ErrorBoundaryState {
  hasError: boolean
  message: string
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false, message: "" }
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, message: error.message }
  }

  componentDidCatch(error: Error) {
    console.error("[ErrorBoundary]", error)
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback

      return (
        <div role="alert" className="flex min-h-[320px] flex-col items-center justify-center gap-4 p-8 text-center">
          <AlertTriangle className="h-10 w-10 text-amber-600" />
          <div>
            <p className="text-lg font-semibold text-foreground">
              页面渲染出错
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              {this.state.message || "发生了未知错误"}
            </p>
          </div>
          <button
            onClick={() => this.setState({ hasError: false, message: "" })}
            className="inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-sm hover:bg-muted"
          >
            <RefreshCw className="h-4 w-4" />
            重试
          </button>
        </div>
      )
    }

    return this.props.children
  }
}
