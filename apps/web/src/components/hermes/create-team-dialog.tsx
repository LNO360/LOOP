"use client"
import { useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { useCreateTeam, useHermesAgents } from "@/hooks/use-hermes"
import type { CustomAgent } from "@/hooks/use-hermes"
import { api } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { cn } from "@/lib/utils"
import { Users, X } from "lucide-react"

interface CreateTeamDialogProps {
  workspaceId: string
  onClose: () => void
  onCreated?: () => void
}

export function CreateTeamDialog({
  workspaceId,
  onClose,
  onCreated,
}: CreateTeamDialogProps) {
  const [step, setStep] = useState<"info" | "members">("info")

  // Step 1 — info
  const [name, setName] = useState("")
  const [goal, setGoal] = useState("")
  const [description, setDescription] = useState("")

  // Step 2 — members
  const [coordinatorId, setCoordinatorId] = useState("")
  const [specialistIds, setSpecialistIds] = useState<Set<string>>(new Set())

  // Error state
  const [error, setError] = useState<string | null>(null)

  const qc = useQueryClient()
  const createMutation = useCreateTeam(workspaceId)
  const { data: agentsData } = useHermesAgents(workspaceId)

  const customAgents: CustomAgent[] = agentsData?.custom ?? []

  const steps = [
    { id: "info" as const, label: "Name & Goal" },
    { id: "members" as const, label: "Members" },
  ]
  const stepIndex = steps.findIndex(s => s.id === step)

  function toggleSpecialist(agentId: string) {
    setSpecialistIds(prev => {
      const next = new Set(prev)
      if (next.has(agentId)) {
        next.delete(agentId)
      } else {
        next.add(agentId)
      }
      return next
    })
  }

  // When coordinator changes, remove that agent from specialists
  function handleCoordinatorChange(agentId: string) {
    setCoordinatorId(agentId)
    if (agentId) {
      setSpecialistIds(prev => {
        const next = new Set(prev)
        next.delete(agentId)
        return next
      })
    }
  }

  const handleSubmit = async () => {
    if (!name.trim()) return
    setError(null)

    try {
      const result = await createMutation.mutateAsync({
        name: name.trim(),
        goal: goal.trim() || undefined,
        description: description.trim() || undefined,
      })

      const newTeamId: string = result?.team?.id
      if (!newTeamId) throw new Error("No team ID returned from server")

      // Add coordinator via direct API call (teamId not known until now)
      if (coordinatorId) {
        await api.post(
          `/workspaces/${workspaceId}/hermes/teams/${newTeamId}/members`,
          { agent_id: coordinatorId, team_role: "coordinator" }
        )
      }

      // Add each specialist
      for (const agentId of Array.from(specialistIds)) {
        await api.post(
          `/workspaces/${workspaceId}/hermes/teams/${newTeamId}/members`,
          { agent_id: agentId, team_role: "specialist" }
        )
      }

      // Invalidate teams query so UI refreshes
      await qc.invalidateQueries({ queryKey: ["hermes-teams", workspaceId] })

      onCreated?.()
      onClose()
    } catch (err) {
      setError((err as Error).message ?? "Failed to create team")
    }
  }

  const isCreating = createMutation.isPending

  // Agents that can be selected as specialists (everyone except the coordinator)
  const specialistCandidates = customAgents.filter(a => a.id !== coordinatorId)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-background rounded-2xl border shadow-xl w-full max-w-lg max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div className="flex items-center gap-2">
            <Users size={16} className="text-primary" />
            <h2 className="text-base font-semibold">Create Team</h2>
          </div>
          <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={onClose}>
            <X size={14} />
          </Button>
        </div>

        {/* Step indicator */}
        <div className="px-6 pt-4 flex gap-1">
          {steps.map((s, i) => (
            <div
              key={s.id}
              className={cn(
                "flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full cursor-pointer transition-colors",
                i <= stepIndex
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground"
              )}
              onClick={() => {
                // Only allow going back, or forward if step 1 is valid
                if (i < stepIndex || (i > stepIndex && name.trim())) {
                  setStep(s.id)
                }
              }}
            >
              {i + 1}. {s.label}
            </div>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {step === "info" && (
            <>
              <div className="rounded-xl border bg-muted/30 p-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-2xl border bg-background shadow-sm">
                    <Users size={18} className="text-foreground/80" />
                  </div>
                  <div>
                    <p className="text-sm font-medium">Team identity</p>
                    <p className="text-xs text-muted-foreground">
                      Give your team a name and define what it should achieve.
                    </p>
                  </div>
                </div>
              </div>

              <div>
                <Label className="text-xs font-medium mb-1.5 block">
                  Name <span className="text-destructive">*</span>
                </Label>
                <Input
                  placeholder="e.g. Finance Team, Ops Crew…"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  autoFocus
                />
              </div>

              <div>
                <Label className="text-xs font-medium mb-1.5 block">
                  Goal <span className="text-muted-foreground">(optional)</span>
                </Label>
                <textarea
                  className="w-full rounded-lg border bg-background px-3 py-2 text-sm resize-none outline-none focus:ring-1 focus:ring-ring min-h-[52px]"
                  rows={2}
                  placeholder="What does this team achieve?"
                  value={goal}
                  onChange={e => setGoal(e.target.value)}
                />
              </div>

              <div>
                <Label className="text-xs font-medium mb-1.5 block">
                  Description <span className="text-muted-foreground">(optional)</span>
                </Label>
                <textarea
                  className="w-full rounded-lg border bg-background px-3 py-2 text-sm resize-none outline-none focus:ring-1 focus:ring-ring min-h-[52px]"
                  rows={2}
                  placeholder="Optional description"
                  value={description}
                  onChange={e => setDescription(e.target.value)}
                />
              </div>
            </>
          )}

          {step === "members" && (
            <>
              {customAgents.length === 0 ? (
                <div className="rounded-xl border bg-muted/30 p-4 text-sm text-muted-foreground">
                  No custom agents yet. Create some agents first, then come back to assign them to a team.
                </div>
              ) : (
                <>
                  <div>
                    <Label className="text-xs font-medium mb-1.5 block">Coordinator</Label>
                    <select
                      className="w-full text-sm border rounded-lg px-3 py-2 bg-background outline-none focus:ring-1 focus:ring-ring"
                      value={coordinatorId}
                      onChange={e => handleCoordinatorChange(e.target.value)}
                    >
                      <option value="">— no coordinator —</option>
                      {customAgents.map(agent => (
                        <option key={agent.id} value={agent.id}>
                          {agent.avatar_emoji} {agent.name}
                        </option>
                      ))}
                    </select>
                    <p className="text-[11px] text-muted-foreground mt-1">
                      The coordinator agent orchestrates the other team members.
                    </p>
                  </div>

                  <div>
                    <Label className="text-xs font-medium mb-1.5 block">Specialists</Label>
                    {specialistCandidates.length === 0 ? (
                      <p className="text-xs text-muted-foreground">
                        {coordinatorId
                          ? "All other agents are assigned as coordinator."
                          : "Select a coordinator first, or add agents here."}
                      </p>
                    ) : (
                      <div className="space-y-1.5">
                        {specialistCandidates.map(agent => (
                          <label
                            key={agent.id}
                            className={cn(
                              "flex items-center gap-2.5 px-3 py-2 rounded-lg border cursor-pointer transition-colors text-sm",
                              specialistIds.has(agent.id)
                                ? "border-primary bg-primary/5"
                                : "border-border hover:bg-muted/50"
                            )}
                          >
                            <input
                              type="checkbox"
                              className="rounded"
                              checked={specialistIds.has(agent.id)}
                              onChange={() => toggleSpecialist(agent.id)}
                            />
                            <span className="text-base leading-none">{agent.avatar_emoji}</span>
                            <span>{agent.name}</span>
                          </label>
                        ))}
                      </div>
                    )}
                  </div>
                </>
              )}

              {/* Preview */}
              <div className="rounded-xl bg-muted/50 p-4 space-y-2">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Preview
                </p>
                <div className="flex items-start gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-2xl border bg-background flex-shrink-0">
                    <Users size={17} className="text-foreground/80" />
                  </div>
                  <div>
                    <p className="font-medium">{name || "Unnamed Team"}</p>
                    {goal && (
                      <p className="text-xs text-muted-foreground mt-0.5">{goal}</p>
                    )}
                    <p className="text-xs text-muted-foreground mt-1">
                      {coordinatorId
                        ? `1 coordinator · ${specialistIds.size} specialist${specialistIds.size !== 1 ? "s" : ""}`
                        : `${specialistIds.size} specialist${specialistIds.size !== 1 ? "s" : ""}, no coordinator`}
                    </p>
                  </div>
                </div>
              </div>
            </>
          )}

          {/* Inline error */}
          {error && (
            <div className="rounded-lg border border-destructive/50 bg-destructive/10 px-3 py-2 text-xs text-destructive">
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t flex items-center justify-between">
          <Button
            variant="ghost"
            size="sm"
            disabled={stepIndex === 0}
            onClick={() => setStep(steps[stepIndex - 1].id)}
          >
            Back
          </Button>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={onClose}>
              Cancel
            </Button>
            {step !== "members" ? (
              <Button
                size="sm"
                disabled={!name.trim()}
                onClick={() => setStep(steps[stepIndex + 1].id)}
              >
                Next
              </Button>
            ) : (
              <Button
                size="sm"
                onClick={handleSubmit}
                disabled={isCreating || !name.trim()}
              >
                {isCreating ? "Creating…" : "Create Team"}
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
