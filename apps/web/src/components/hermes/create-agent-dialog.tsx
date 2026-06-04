"use client"
import { useState } from "react"
import { useCreateAgent, streamHermes, useAgentTeams, useAddTeamMember } from "@/hooks/use-hermes"
import { ModelPicker } from "@/components/hermes/model-picker"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { cn } from "@/lib/utils"
import { Cpu, X, Sparkles, Loader2 } from "lucide-react"

const SCHEDULE_PRESETS = [
  { label: "Every 2 hours", value: "every 2 hours" },
  { label: "Daily at 9am", value: "0 9 * * *" },
  { label: "Weekly Monday", value: "0 9 * * 1" },
  { label: "Weekly Friday", value: "0 16 * * 5" },
  { label: "Manual only", value: "" },
]

const SOUL_TEMPLATE = `You are a custom Loop agent. Your job is to:

1. Start each session by calling lno_list_workspaces to discover all workspace IDs
2. [Describe what this agent monitors or does]
3. Take the following actions: [List specific actions]

## Reporting
- Send a notification via lno_create_notification if you find [condition]
- Store key findings with lno_upsert_workspace_memory under key "[your-namespace].*"

## Decision Rules
- [Add specific rules for when to act vs observe]
`

const AGENT_TEMPLATES = [
  {
    label: "Finance Scout", emoji: "💰", schedule: "0 7 * * *",
    soul: `# Finance Scout\n\n## Team Coordination\n1. Read team.handoff.finance-scout\n2. If no handoff: run finance reconcile\n3. Write team.report.finance-scout\n\n## Your Job\n- finance_get_overview\n- finance_list_transactions last 7 days\n- gmail_search "from:razorpay"\n\n## Memory\nNamespace: finance.*`
  },
  {
    label: "PM", emoji: "📊", schedule: "0 9 * * 1",
    soul: `# Project Manager\n\n## Team Coordination\n1. Read team.handoff.project-manager\n2. Write team.report.project-manager\n\n## Your Job\n- lno_list_projects + lno_list_overdue_tasks\n- Flag blockers\n\n## Memory\nNamespace: pm.*`
  },
  {
    label: "GitHub Watcher", emoji: "🐙", schedule: "0 10 * * *",
    soul: `# GitHub Watcher\n\n## Team Coordination\n1. Read team.handoff.github-watcher\n2. Write team.report.github-watcher\n\n## Your Job\n- github_list_prs + github_list_issues\n- Flag stale PRs (>7 days)\n\n## Memory\nNamespace: github.*`
  },
  {
    label: "Ops Monitor", emoji: "🔍", schedule: "every 2 hours",
    soul: `# Ops Monitor\n\n## Your Job\n- lno_get_workspace_snapshot\n- lno_list_overdue_tasks\n- lno_create_notification for issues\n\n## Memory\nNamespace: ops.*`
  },
  {
    label: "Inbox Triage", emoji: "📬", schedule: "0 8 * * *",
    soul: `# Inbox Triage\n\n## Team Coordination\n1. Read team.handoff.inbox-triage\n2. Write team.report.inbox-triage\n\n## Your Job\n- gmail_list_inbox\n- Label urgent, archive noise\n\n## Memory\nNamespace: inbox.*`
  },
  { label: "Custom", emoji: "🤖", schedule: "", soul: SOUL_TEMPLATE },
]

interface CreateAgentDialogProps {
  workspaceId: string
  onClose: () => void
  onCreated?: () => void
}

export function CreateAgentDialog({
  workspaceId,
  onClose,
  onCreated,
}: CreateAgentDialogProps) {
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [soulMd, setSoulMd] = useState(SOUL_TEMPLATE)
  const [schedule, setSchedule] = useState("")
  const [model, setModel] = useState("")
  const [step, setStep] = useState<"identity" | "personality" | "schedule">("identity")

  // Feature A — template chips
  const [activeTemplate, setActiveTemplate] = useState("Custom")

  // Feature B — AI soul generation
  const [aiDesc, setAiDesc] = useState("")
  const [isGenerating, setIsGenerating] = useState(false)

  // Feature C — team assignment
  const [teamId, setTeamId] = useState("")
  const [teamRole, setTeamRole] = useState<"coordinator" | "specialist">("specialist")

  const createMutation = useCreateAgent(workspaceId)
  const { data: teamsData } = useAgentTeams(workspaceId)
  const addTeamMemberMutation = useAddTeamMember(workspaceId, teamId || "placeholder")

  function handleGenerateSoul() {
    if (!aiDesc.trim()) return
    setIsGenerating(true)
    setSoulMd("")
    const prompt = `Generate a Hermes agent soul_md for an agent that: "${aiDesc}". Include: role section, memory namespace, which MCP tools to use, decision rules, team coordination section. Return only markdown, no preamble.`
    streamHermes(
      workspaceId,
      prompt,
      (chunk) => setSoulMd((prev) => prev + chunk),
      () => setIsGenerating(false),
      (err) => { setIsGenerating(false); console.error(err) }
    )
  }

  const handleCreate = async () => {
    if (!name.trim() || !soulMd.trim()) return
    const result = await createMutation.mutateAsync({
      name: name.trim(),
      description: description.trim() || undefined,
      soul_md: soulMd,
      schedule: schedule || undefined,
      model: model || undefined,
    })
    const newAgentId = result?.agent?.id
    if (teamId && newAgentId) {
      await addTeamMemberMutation.mutateAsync({ agent_id: newAgentId, team_role: teamRole })
    }
    onCreated?.()
    onClose()
  }

  const steps = [
    { id: "identity" as const, label: "Identity" },
    { id: "personality" as const, label: "Personality" },
    { id: "schedule" as const, label: "Schedule" },
  ]
  const stepIndex = steps.findIndex(s => s.id === step)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-background rounded-2xl border shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div className="flex items-center gap-2">
            <Sparkles size={16} className="text-primary" />
            <h2 className="text-base font-semibold">Create Agent</h2>
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
              onClick={() => setStep(s.id)}
            >
              {i + 1}. {s.label}
            </div>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {step === "identity" && (
            <>
              <div className="rounded-xl border bg-muted/30 p-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-2xl border bg-background shadow-sm">
                    <Cpu size={18} className="text-foreground/80" />
                  </div>
                  <div>
                    <p className="text-sm font-medium">Agent identity</p>
                    <p className="text-xs text-muted-foreground">
                      LNO will style this agent with the workspace icon system.
                    </p>
                  </div>
                </div>
              </div>

              {/* Feature A — Role template chips */}
              <div>
                <Label className="text-xs font-medium mb-1.5 block">Start from a template</Label>
                <div className="flex flex-wrap gap-2 mb-4">
                  {AGENT_TEMPLATES.map((t) => (
                    <button
                      key={t.label}
                      type="button"
                      onClick={() => {
                        setName(t.label === "Custom" ? "" : t.label)
                        setSoulMd(t.soul)
                        setSchedule(t.schedule)
                        setActiveTemplate(t.label)
                      }}
                      className={cn(
                        "flex items-center gap-1 px-2 py-1 rounded-md text-xs border transition-colors",
                        activeTemplate === t.label
                          ? "bg-primary text-primary-foreground border-primary"
                          : "bg-muted/50 border-border hover:bg-muted"
                      )}
                    >
                      <span>{t.emoji}</span>
                      <span>{t.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <Label className="text-xs font-medium mb-1.5 block">Name</Label>
                <Input
                  placeholder="e.g. Research Scout, Code Reviewer…"
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

          {step === "personality" && (
            <div>
              <Label className="text-xs font-medium mb-1.5 block">
                Personality & Instructions
                <span className="ml-2 text-muted-foreground font-normal">
                  This is the full soul of your agent. Be specific.
                </span>
              </Label>

              {/* Feature B — AI soul generation */}
              <div className="flex gap-2 mb-2">
                <input
                  className="flex-1 text-sm border rounded px-2 py-1.5 bg-background"
                  placeholder="Describe what this agent should do..."
                  value={aiDesc}
                  onChange={(e) => setAiDesc(e.target.value)}
                  disabled={isGenerating}
                />
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={!aiDesc.trim() || isGenerating}
                  onClick={handleGenerateSoul}
                >
                  {isGenerating ? <Loader2 className="h-3 w-3 animate-spin" /> : "Generate"}
                </Button>
              </div>

              <textarea
                className="w-full h-80 rounded-xl border bg-muted/30 px-3 py-2.5 text-sm font-mono resize-none outline-none focus:ring-1 focus:ring-ring"
                value={soulMd}
                onChange={e => setSoulMd(e.target.value)}
                spellCheck={false}
                disabled={isGenerating}
              />
              <p className="text-[11px] text-muted-foreground mt-1.5">
                You can also ask the AI assistant in chat to update this agent skill later.
              </p>
            </div>
          )}

          {step === "schedule" && (
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

              {/* Feature C — Team assignment */}
              {teamsData && teamsData.teams.length > 0 && (
                <div className="mt-4 space-y-2">
                  <label className="text-sm font-medium">Assign to team (optional)</label>
                  <select
                    className="w-full text-sm border rounded px-2 py-1.5 bg-background"
                    value={teamId}
                    onChange={(e) => setTeamId(e.target.value)}
                  >
                    <option value="">— no team —</option>
                    {teamsData.teams.map((t) => (
                      <option key={t.id} value={t.id}>{t.name}</option>
                    ))}
                  </select>
                  {teamId && (
                    <div className="flex gap-3 text-sm">
                      <label className="flex items-center gap-1.5 cursor-pointer">
                        <input type="radio" name="team_role" value="specialist" checked={teamRole === "specialist"} onChange={() => setTeamRole("specialist")} />
                        Specialist
                      </label>
                      <label className="flex items-center gap-1.5 cursor-pointer">
                        <input type="radio" name="team_role" value="coordinator" checked={teamRole === "coordinator"} onChange={() => setTeamRole("coordinator")} />
                        Coordinator
                      </label>
                    </div>
                  )}
                </div>
              )}

              {/* Preview */}
              <div className="rounded-xl bg-muted/50 p-4 space-y-2">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Preview
                </p>
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-2xl border bg-background">
                    <Cpu size={17} className="text-foreground/80" />
                  </div>
                  <div>
                    <p className="font-medium">{name || "Unnamed Agent"}</p>
                    <p className="text-xs text-muted-foreground">
                      {schedule ? `Runs: ${schedule}` : "Manual runs only"}
                      {model ? ` · ${model}` : ""}
                    </p>
                  </div>
                </div>
              </div>
            </>
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
            {step !== "schedule" ? (
              <Button
                size="sm"
                disabled={step === "identity" && !name.trim()}
                onClick={() => setStep(steps[stepIndex + 1].id)}
              >
                Next
              </Button>
            ) : (
              <Button
                size="sm"
                onClick={handleCreate}
                disabled={createMutation.isPending || !name.trim() || !soulMd.trim()}
              >
                {createMutation.isPending ? "Creating…" : "Create Agent"}
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
