import { type ReactNode } from "react"

import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { cn } from "@/lib/utils"

export function FormField({
  label,
  htmlFor,
  description,
  children,
  className,
  descriptionClassName,
}: {
  label?: ReactNode
  htmlFor?: string
  description?: ReactNode
  children: ReactNode
  className?: string
  descriptionClassName?: string
}) {
  return (
    <div className={cn("form-field", className)}>
      {label ? <Label htmlFor={htmlFor}>{label}</Label> : null}
      {children}
      {description ? <p className={cn("form-hint", descriptionClassName)}>{description}</p> : null}
    </div>
  )
}

export function CheckboxField({
  id,
  checked,
  onCheckedChange,
  label,
  description,
  className,
}: {
  id?: string
  checked: boolean
  onCheckedChange: (checked: boolean) => void
  label: ReactNode
  description?: ReactNode
  className?: string
}) {
  return (
    <label htmlFor={id} className={cn("form-checkbox-row cursor-pointer", className)}>
      <Checkbox id={id} checked={checked} onCheckedChange={(value) => onCheckedChange(Boolean(value))} />
      <div className="min-w-0 space-y-1">
        <div className="form-checkbox-label">{label}</div>
        {description ? <div className="form-hint">{description}</div> : null}
      </div>
    </label>
  )
}
