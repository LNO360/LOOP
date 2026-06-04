"use client"

import { useState } from "react"
import { Check, ChevronDown, User, X } from "lucide-react"
import { cn } from "@/lib/utils"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Button } from "@/components/ui/button"

interface Member {
  id: string
  name: string
}

interface MemberMultiSelectProps {
  members: Member[]
  value: string[]
  onChange: (ids: string[]) => void
  placeholder?: string
  className?: string
}

export function MemberMultiSelect({
  members,
  value,
  onChange,
  placeholder = "Assign people…",
  className,
}: MemberMultiSelectProps) {
  const [open, setOpen] = useState(false)
  const selected = members.filter((m) => value.includes(m.id))

  function toggle(id: string) {
    if (value.includes(id)) {
      onChange(value.filter((v) => v !== id))
    } else {
      onChange([...value, id])
    }
  }

  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            type="button"
            variant="outline"
            className="h-9 w-full justify-between font-normal text-sm"
          >
            <span className="flex items-center gap-2 truncate text-muted-foreground">
              <User size={14} />
              {selected.length === 0
                ? placeholder
                : `${selected.length} assigned`}
            </span>
            <ChevronDown size={14} className="shrink-0 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[var(--radix-popover-trigger-width)] p-1" align="start">
          {members.length === 0 ? (
            <p className="px-2 py-2 text-xs text-muted-foreground">No members</p>
          ) : (
            members.map((m) => {
              const checked = value.includes(m.id)
              return (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => toggle(m.id)}
                  className={cn(
                    "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-muted",
                    checked && "bg-muted/80"
                  )}
                >
                  <span
                    className={cn(
                      "flex h-4 w-4 shrink-0 items-center justify-center rounded border",
                      checked ? "bg-accent border-accent text-white" : "border-input"
                    )}
                  >
                    {checked && <Check size={10} />}
                  </span>
                  {m.name}
                </button>
              )
            })
          )}
        </PopoverContent>
      </Popover>

      {selected.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {selected.map((m) => (
            <span
              key={m.id}
              className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs"
            >
              {m.name}
              <button
                type="button"
                onClick={() => onChange(value.filter((v) => v !== m.id))}
                className="rounded-full hover:bg-background/80"
                aria-label={`Remove ${m.name}`}
              >
                <X size={10} />
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
