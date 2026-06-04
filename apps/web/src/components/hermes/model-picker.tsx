"use client"
import { useState } from "react"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

interface ModelOption {
  id: string
  label: string
  tier: "free" | "paid"
}

const CURATED_MODELS: ModelOption[] = [
  // Free tier
  { id: "deepseek/deepseek-v4-flash:free",                    label: "DeepSeek V4 Flash",         tier: "free" },
  { id: "deepseek/deepseek-r1:free",                          label: "DeepSeek R1",               tier: "free" },
  { id: "meta-llama/llama-3.3-70b-instruct:free",             label: "Llama 3.3 70B",             tier: "free" },
  { id: "google/gemma-4-31b-it:free",                         label: "Gemma 4 31B",               tier: "free" },
  { id: "nousresearch/hermes-3-llama-3.1-405b:free",          label: "Hermes 3 Llama 405B",       tier: "free" },
  // Paid
  { id: "anthropic/claude-sonnet-4-6",                        label: "Claude Sonnet 4.6",         tier: "paid" },
  { id: "anthropic/claude-opus-4-7",                          label: "Claude Opus 4.7",           tier: "paid" },
  { id: "openai/gpt-4o",                                      label: "GPT-4o",                    tier: "paid" },
  { id: "openai/gpt-4o-mini",                                 label: "GPT-4o Mini",               tier: "paid" },
]

const CUSTOM_VALUE = "__custom__"

interface ModelPickerProps {
  value: string           // model ID or empty string (= use Hermes default)
  onChange: (v: string) => void
  className?: string
  defaultOptionLabel?: string   // label for the empty-value option (default = Hermes config default)
}

export function ModelPicker({ value, onChange, className, defaultOptionLabel }: ModelPickerProps) {
  const isCustom = !!value && !CURATED_MODELS.find(m => m.id === value)
  const [showCustom, setShowCustom] = useState(isCustom)

  const selectValue = isCustom ? CUSTOM_VALUE : (value || "")

  function handleSelectChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const v = e.target.value
    if (v === CUSTOM_VALUE) {
      setShowCustom(true)
      onChange("")
    } else {
      setShowCustom(false)
      onChange(v)
    }
  }

  return (
    <div className={cn("space-y-2", className)}>
      <select
        value={selectValue}
        onChange={handleSelectChange}
        className="w-full rounded-lg border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
      >
        <option value="">{defaultOptionLabel ?? "Hermes default (from config.yaml)"}</option>
        <optgroup label="── Free tier ──">
          {CURATED_MODELS.filter(m => m.tier === "free").map(m => (
            <option key={m.id} value={m.id}>{m.label} ({m.id})</option>
          ))}
        </optgroup>
        <optgroup label="── Paid ──">
          {CURATED_MODELS.filter(m => m.tier === "paid").map(m => (
            <option key={m.id} value={m.id}>{m.label}</option>
          ))}
        </optgroup>
        <optgroup label="── Custom ──">
          <option value={CUSTOM_VALUE}>Type model ID…</option>
        </optgroup>
      </select>

      {showCustom && (
        <Input
          placeholder="e.g. mistralai/mistral-7b-instruct:free"
          value={value}
          onChange={e => onChange(e.target.value)}
          autoFocus
        />
      )}
    </div>
  )
}
