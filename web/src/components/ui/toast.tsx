"use client"

import { AlertCircle, CheckCircle2, Info, LoaderCircle, TriangleAlert, X } from "lucide-react"
import { Toaster as SonnerToaster, toast, type ToastClassnames, type ToasterProps } from "sonner"

const TOAST_CLASSNAMES: ToastClassnames = {
  toast: "toast-shell",
  title: "toast-title",
  description: "toast-description",
  content: "toast-content",
  icon: "toast-icon",
  closeButton: "toast-close",
  actionButton: "toast-action",
  cancelButton: "toast-cancel",
  success: "toast-success",
  error: "toast-error",
  info: "toast-info",
  warning: "toast-warning",
  loading: "toast-loading",
  default: "toast-default",
}

export function AppToaster({
  toastOptions,
  icons,
  ...props
}: ToasterProps) {
  const mergedClassNames: ToastClassnames = {
    ...TOAST_CLASSNAMES,
    ...toastOptions?.classNames,
  }

  return (
    <SonnerToaster
      theme="light"
      position="top-right"
      richColors={false}
      expand={false}
      closeButton
      visibleToasts={4}
      offset={24}
      mobileOffset={16}
      containerAriaLabel="通知"
      icons={{
        success: <CheckCircle2 className="h-4 w-4" />,
        error: <AlertCircle className="h-4 w-4" />,
        info: <Info className="h-4 w-4" />,
        warning: <TriangleAlert className="h-4 w-4" />,
        loading: <LoaderCircle className="h-4 w-4 animate-spin" />,
        close: <X className="h-4 w-4" />,
        ...icons,
      }}
      toastOptions={{
        ...toastOptions,
        duration: 4200,
        unstyled: true,
        classNames: mergedClassNames,
      }}
      {...props}
    />
  )
}

export { toast }
