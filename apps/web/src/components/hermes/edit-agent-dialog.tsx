"use client"
import { useState, useEffect } from "react"
import { useUpdateAgent } from "@/hooks/use-hermes"
import { ModelPicker } from "@/components/hermes/model-picker"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { cn } from "@/lib/utils"
import { X, Sparkles } from "lucide-react"
import type { CustomAgent } from "@/hooks/use-hermes"

const SCHEDULE_PRESETS = [
  { label: "Every 2 hours", value: "every 2 hours" },
  { label: "Daily at 9am", value: "0 9 * * *" },
  { label: "Weekly Monday", value: "0 9 * * 1" },
  { label: "Weekly Friday", value: "0 16 * * 5" },
  { label: "Manual only", value: "" },
]

interface EditAgentDialogProps {
  workspaceId: string
  agent: CustomAgent
  onClose: () => void
  onSaved?: () => void
}

export function EditAgentDialog({
  workspaceId,
  agent,
  onClose,
  onSaved,
}: EditAgentDialogProps) {
  const [name, setName] = useState(agent.name)
  const [description, setDescription] = useState(agent.description ?? "")
  const [soulMd, setSoulMd] = useState(agent.soul_md ?? "")
  const [schedule, setSchedule] = useState(agent.schedule ?? "")
  const [model, setModel] = useState(agent.model ?? "")
  const [tab, setTab] = useState<"identity" | "personality" | "schedule">("identity")

  const updateMutation = useUpdateAgent(workspaceId, agent.id)

  const handleSave = async () => {
    await updateMutation.mutateAsync({
      name: name.trim(),
      description: description.trim() || undefined,
      soul_md: soulMd,
      schedule: schedule || undefined,
      model: model || undefined,
    })
    onSaved?.()
    onClose()
  }

  const tabs = [
    { id: "identity" as const, label: "Identity" },
    { id: "personality" as const, label: "Personality" },
    { id: "schedule" as const, label: "Schedule" },
  ]
  const tabIndex = tabs.findIndex(t => t.id === tab)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-background rounded-2xl border shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div className="flex items-center gap-2">
            <Sparkles size={16} className="text-primary" />
            <h2 className="text-base font-semibold">Edit Agent</h2>
            <span className="text-sm text-muted-foreground">— {agent.name}</span>
          </div>
          <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={onClose}>
            <X size={14} />
          </Button>
        </div>

        {/* Step indicator */}
        <div className="px-6 pt-4 flex gap-1">
          {tabs.map((t, i) => (
            <button
              key={t.id}
              className={cn(
                "flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full cursor-pointer transition-colors",
                i <= tabIndex
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground"
              )}
              onClick={() => setTab(t.id)}
            >
              {i + 1}. {t.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {tab === "identity" && (
            <>
              <div>
                <Label className="text-xs font-medium mb-1.5 block">Name</Label>
                <Input
                  value={name}
                  onChange={e => setName(e.target.value)}
                  autoFocus
                />
              </div>
              <div>
                <Label className="text-xs font-medium mb-1.5 block">
                  Description <span className="text-muted-foreground">(optional)</span>
                </Label>
                <Input
                  placeholder="What does this agent do?"
                  value={description}
                  onChange={e => setDescription(e.target.value)}
                />
              </div>
            </>
          )}

          {tab === "personality" && (
            <div>
              <Label className="text-xs font-medium mb-1.5 block">
                Personality & Instructions
                <span className="ml-2 text-muted-foreground font-normal">
                  This is the full soul of your agent.
                </span>
              </Label>
              <textarea
                className="w-full h-80 rounded-xl border bg-muted/30 px-3 py-2.5 text-sm font-mono resize-none outline-none focus:ring-1 focus:ring-ring"
                value={soulMd}
                onChange={e => setSoulMd(e.target.value)}
                spellCheck={false}
              />
            </div>
          )}

          {tab === "schedule" && (
            <>
              <div>
                <Label className="text-xs font-medium mb-1.5 block">Run Schedule</Label>
                <div className="grid grid-cols-2 gap-2">
                  {SCHEDULE_PRESETS.map(p => (
                    <button
                      key={p.value}
                      onClick={() => setSchedule(p.value)}
                      className={cn(
                        "px-3 py-2 rounded-lg border text-sm text-left transition-colors",
                        schedule === p.value
                          ? "border-primary bg-primary/10 text-primary"
                          : "hover:bg-muted"
                      )}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
                <Input
                  className="mt-2"
                  placeholder="Or enter custom cron: 0 9 * * 1"
                  value={schedule}
                  onChange={e => setSchedule(e.target.value)}
                />
              </div>

              <div>
                <Label className="text-xs font-medium mb-1.5 block">
                  Model Override <span className="text-muted-foreground">(optional — blank = workspace default)</span>
                </Label>
                <ModelPicker value={model} onChange={setModel} />
              </div>

              {updateMutation.error && (
                <p className="text-xs text-destructive">
                  Error: {(updateMutation.error as Error).message}
                </p>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t flex items-center justify-between">
          <Button
            variant="ghost"
            size="sm"
            disabled={tabIndex === 0}
            onClick={() => setTab(tabs[tabIndex - 1].id)}
          >
            Back
          </Button>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={onClose}>
              Cancel
            </Button>
            {tab !== "schedule" ? (
              <Button
                size="sm"
                onClick={() => setTab(tabs[tabIndex + 1].id)}
              >
                Next
              </Button>
            ) : (
              <Button
                size="sm"
                onClick={handleSave}
                disabled={updateMutation.isPending || !name.trim()}
              >
                {updateMutation.isPending ? "Saving…" : "Save Changes"}
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
