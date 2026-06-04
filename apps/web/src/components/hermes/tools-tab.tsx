"use client"

import { useMemo, useState } from "react"
import { AlertTriangle, RotateCcw, Save, Wrench } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { HermesFileResult } from "@/hooks/use-hermes"

/**
 * Tool picker for the Hermes agent.
 *
 * Hermes exposes one MCP tool definition per turn for every tool in
 * `mcp_servers.lno-os.tools.include`. Each definition costs ~100–150 tokens of
 * input on every turn — so fewer enabled tools = a smaller prompt, especially on
 * cache-cold turns. This panel edits that `include:` list directly in config.yaml
 * (via the same raw-config read/write the "Raw engine config" tab uses).
 *
 * Scope note: config.yaml is GLOBAL (not per-workspace). In-app chat picks up
 * changes on the next message; the Telegram gateway needs a Hermes restart.
 */

// Rough per-tool input-token cost of an MCP tool definition (schema + description).
const TOKENS_PER_TOOL = 130

interface CatalogTool {
  name: string
  label: string
}
interface CatalogGroup {
  category: string
  hint?: string
  tools: CatalogTool[]
}

// Full catalog of tools the LNO MCP server can expose. Anything checked here is
// written to the `include:` allowlist; anything unchecked is removed from it.
const TOOL_CATALOG: CatalogGroup[] = [
  {
    category: "LNO — Tasks & Projects",
    tools: [
      { name: "lno_list_workspaces", label: "List workspaces" },
      { name: "lno_get_workspace_snapshot", label: "Workspace snapshot" },
      { name: "lno_list_tasks", label: "List tasks" },
      { name: "lno_list_overdue_tasks", label: "List overdue tasks" },
      { name: "lno_create_task", label: "Create task" },
      { name: "lno_update_task", label: "Update task" },
      { name: "lno_list_projects", label: "List projects" },
      { name: "lno_create_project", label: "Create project" },
      { name: "lno_update_project", label: "Update project" },
      { name: "lno_get_channel_messages", label: "Read channel messages" },
      { name: "lno_send_channel_message", label: "Send channel message" },
      { name: "lno_create_notification", label: "Create notification" },
    ],
  },
  {
    category: "LNO — Memory",
    tools: [
      { name: "lno_get_workspace_memory", label: "Get memory" },
      { name: "lno_search_workspace_memory", label: "Search memory (keyword)" },
      { name: "lno_semantic_search_workspace_memory", label: "Search memory (semantic)" },
      { name: "lno_upsert_workspace_memory", label: "Upsert memory" },
      { name: "lno_delete_workspace_memory", label: "Delete memory" },
      { name: "lno_sync_hermes_memory", label: "Sync Hermes memory" },
    ],
  },
  {
    category: "LNO — Efficiency (feedback & runbooks)",
    tools: [
      { name: "lno_submit_feedback", label: "Submit feedback" },
      { name: "lno_get_feedback", label: "Get feedback" },
      { name: "lno_create_runbook", label: "Create runbook" },
      { name: "lno_list_runbooks", label: "List runbooks" },
      { name: "lno_execute_runbook", label: "Execute runbook" },
    ],
  },
  {
    category: "LNO — Self-modification",
    hint: "Lets Hermes edit its own personality/skills/agents from chat.",
    tools: [
      { name: "lno_read_soul_md", label: "Read SOUL.md" },
      { name: "lno_write_soul_md", label: "Write SOUL.md" },
      { name: "lno_list_skills", label: "List skills" },
      { name: "lno_read_skill", label: "Read skill" },
      { name: "lno_create_skill", label: "Create skill" },
      { name: "lno_delete_skill", label: "Delete skill" },
      { name: "lno_create_agent", label: "Create agent" },
      { name: "lno_list_agents", label: "List agents" },
    ],
  },
  {
    category: "LNO — Teams",
    tools: [
      { name: "lno_list_teams", label: "List teams" },
      { name: "lno_create_team", label: "Create team" },
      { name: "lno_assign_agent_to_team", label: "Assign agent to team" },
      { name: "lno_remove_team_member", label: "Remove team member" },
    ],
  },
  {
    category: "LNO — Proposed actions",
    tools: [
      { name: "lno_list_proposed_actions", label: "List proposed actions" },
      { name: "lno_approve_proposed_action", label: "Approve action" },
      { name: "lno_reject_proposed_action", label: "Reject action" },
    ],
  },
  {
    category: "LNO — Boardroom",
    tools: [
      { name: "lno_list_boardroom_personas", label: "List personas" },
      { name: "lno_create_boardroom", label: "Create boardroom" },
      { name: "lno_start_boardroom", label: "Start boardroom" },
    ],
  },
  {
    category: "Gmail",
    tools: [
      { name: "gmail_list_inbox", label: "List inbox" },
      { name: "gmail_search", label: "Search" },
      { name: "gmail_get_email", label: "Read email" },
      { name: "gmail_send", label: "Send email" },
      { name: "gmail_create_draft", label: "Create draft" },
      { name: "gmail_add_label", label: "Add label" },
      { name: "gmail_archive", label: "Archive" },
    ],
  },
  {
    category: "Google Drive",
    tools: [
      { name: "gdrive_search", label: "Search" },
      { name: "gdrive_list_folder", label: "List folder" },
      { name: "gdrive_read_file", label: "Read file" },
      { name: "gdrive_get_file_info", label: "File info" },
      { name: "gdrive_upload_file", label: "Upload file" },
    ],
  },
  {
    category: "Google Calendar & Meet",
    tools: [
      { name: "gcal_list_events", label: "List events" },
      { name: "gcal_find_free_slots", label: "Find free slots" },
      { name: "gcal_list_calendars", label: "List calendars" },
      { name: "gcal_create_event", label: "Create event" },
      { name: "gcal_create_event_with_meet", label: "Create event + Meet" },
      { name: "gcal_update_event", label: "Update event" },
      { name: "gcal_delete_event", label: "Delete event" },
      { name: "gmeet_list_upcoming", label: "Upcoming Meet links" },
    ],
  },
  {
    category: "Google Sheets",
    tools: [
      { name: "gsheets_list_spreadsheets", label: "List spreadsheets" },
      { name: "gsheets_get_metadata", label: "Get metadata" },
      { name: "gsheets_read_range", label: "Read range" },
      { name: "gsheets_append_row", label: "Append row" },
      { name: "gsheets_update_cells", label: "Update cells" },
    ],
  },
  {
    category: "GitHub",
    tools: [
      { name: "github_list_repos", label: "List repos" },
      { name: "github_list_issues", label: "List issues" },
      { name: "github_get_issue", label: "Get issue" },
      { name: "github_list_prs", label: "List PRs" },
      { name: "github_get_pr", label: "Get PR" },
      { name: "github_search_code", label: "Search code" },
      { name: "github_create_issue", label: "Create issue" },
      { name: "github_add_issue_comment", label: "Comment on issue/PR" },
    ],
  },
  {
    category: "Finance",
    tools: [
      { name: "finance_get_overview", label: "Overview" },
      { name: "finance_get_summary", label: "Summary" },
      { name: "finance_list_accounts", label: "List accounts" },
      { name: "finance_list_transactions", label: "List transactions" },
      { name: "finance_list_unpaid_invoices", label: "Unpaid invoices" },
      { name: "finance_list_categories", label: "List categories" },
      { name: "finance_create_transaction", label: "Create transaction" },
      { name: "finance_update_transaction", label: "Update transaction" },
      { name: "finance_delete_transaction", label: "Delete transaction" },
      { name: "finance_create_invoice", label: "Create invoice" },
      { name: "finance_mark_invoice_paid", label: "Mark invoice paid" },
    ],
  },
  {
    category: "Web research",
    tools: [
      { name: "web_search", label: "Web search" },
      { name: "web_fetch_page", label: "Fetch page" },
      { name: "web_research", label: "Deep research" },
    ],
  },
]

const ALL_TOOL_NAMES = TOOL_CATALOG.flatMap((g) => g.tools.map((t) => t.name))

/**
 * Parse the enabled tool names from the `include:` block of config.yaml.
 * Returns the set of tool names currently in the allowlist.
 */
export function parseEnabledTools(content: string): Set<string> {
  const lines = content.split(/\r?\n/)
  const includeIdx = lines.findIndex((l) => /^\s*include:\s*$/.test(l))
  if (includeIdx === -1) return new Set()

  const enabled = new Set<string>()
  for (let i = includeIdx + 1; i < lines.length; i += 1) {
    const line = lines[i]
    // Block continues only while lines are indented ≥8 spaces with content.
    if (!/^\s{8,}\S/.test(line)) break
    const m = line.match(/^\s{8,}-\s+([A-Za-z0-9_]+)/)
    if (m) enabled.add(m[1])
  }
  return enabled
}

/**
 * Rewrite the `include:` block to exactly the given enabled tools, grouped by
 * the catalog (with category comments). Everything else in the file is preserved.
 */
export function writeEnabledTools(content: string, enabled: Set<string>): string {
  const lines = content.split(/\r?\n/)
  const includeIdx = lines.findIndex((l) => /^\s*include:\s*$/.test(l))
  if (includeIdx === -1) return content

  const indentMatch = lines[includeIdx].match(/^(\s*)include:/)
  const itemIndent = (indentMatch?.[1].length ?? 6) + 2
  const pad = " ".repeat(itemIndent)

  // Determine the extent of the existing include body (contiguous ≥8-indent lines).
  let end = includeIdx + 1
  while (end < lines.length && /^\s{8,}\S/.test(lines[end])) end += 1

  // Render the new body grouped by catalog; only show a group that has ≥1 enabled.
  const body: string[] = []
  for (const group of TOOL_CATALOG) {
    const on = group.tools.filter((t) => enabled.has(t.name))
    if (on.length === 0) continue
    body.push(`${pad}# ${group.category}`)
    for (const t of on) body.push(`${pad}- ${t.name}`)
  }

  const next = [...lines]
  next.splice(includeIdx + 1, end - (includeIdx + 1), ...body)
  return next.join("\n")
}

export function ToolsTab({ configHook }: { configHook: HermesFileResult }) {
  const initial = useMemo(() => parseEnabledTools(configHook.content), [configHook.content])
  const [enabled, setEnabled] = useState<Set<string>>(() => new Set(initial))
  const [savedMsg, setSavedMsg] = useState<string | null>(null)

  // Any tool present in the file but not in our catalog — keep it untouched on save.
  const unknownEnabled = useMemo(
    () => [...initial].filter((n) => !ALL_TOOL_NAMES.includes(n)),
    [initial],
  )

  const dirty = useMemo(() => {
    if (enabled.size !== initial.size) return true
    for (const n of enabled) if (!initial.has(n)) return true
    return false
  }, [enabled, initial])

  function toggle(name: string) {
    setSavedMsg(null)
    setEnabled((prev) => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  function toggleGroup(group: CatalogGroup, on: boolean) {
    setSavedMsg(null)
    setEnabled((prev) => {
      const next = new Set(prev)
      for (const t of group.tools) {
        if (on) next.add(t.name)
        else next.delete(t.name)
      }
      return next
    })
  }

  async function save() {
    // Preserve any unknown enabled tools so we never silently drop them.
    const toWrite = new Set(enabled)
    for (const n of unknownEnabled) toWrite.add(n)
    const nextConfig = writeEnabledTools(configHook.content, toWrite)
    try {
      await configHook.save(nextConfig)
      setSavedMsg("Saved. In-app chat uses it on the next message; restart Hermes for Telegram.")
    } catch {
      setSavedMsg("Save failed — check the raw config tab.")
    }
  }

  const count = enabled.size
  const estTokens = (count * TOKENS_PER_TOOL).toLocaleString()

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <Wrench size={15} /> Agent tools
          </h3>
          <p className="text-xs text-muted-foreground mt-1 max-w-xl">
            Every enabled tool is sent to the model on <em>every turn</em> (~{TOKENS_PER_TOOL} tokens
            each). Turn off what you don&apos;t use in chat to shrink the prompt. Applies org-wide.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setEnabled(new Set(initial))
              setSavedMsg(null)
            }}
            disabled={!dirty || configHook.isSaving}
          >
            <RotateCcw size={14} className="mr-1.5" />
            Reset
          </Button>
          <Button size="sm" onClick={save} disabled={!dirty || configHook.isSaving}>
            <Save size={14} className="mr-1.5" />
            {configHook.isSaving ? "Saving..." : "Save"}
          </Button>
        </div>
      </div>

      <div className="rounded-lg border bg-muted/30 px-3 py-2 text-xs text-muted-foreground flex flex-wrap items-center gap-x-4 gap-y-1">
        <span>
          <span className="font-medium text-foreground">{count}</span> tools enabled
        </span>
        <span>
          ≈ <span className="font-medium text-foreground">{estTokens}</span> tokens/turn in tool
          definitions
        </span>
        {savedMsg && <span className="text-emerald-600 dark:text-emerald-400">{savedMsg}</span>}
      </div>

      {unknownEnabled.length > 0 && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
          <AlertTriangle size={14} className="inline mr-1.5 align-text-bottom" />
          {unknownEnabled.length} enabled tool(s) not in this list (
          {unknownEnabled.join(", ")}) will be kept as-is. Edit them in the raw config tab.
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        {TOOL_CATALOG.map((group) => {
          const onCount = group.tools.filter((t) => enabled.has(t.name)).length
          const allOn = onCount === group.tools.length
          return (
            <div key={group.category} className="rounded-xl border bg-card p-3 space-y-2">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <p className="text-xs font-semibold">{group.category}</p>
                  {group.hint && (
                    <p className="text-[11px] text-muted-foreground mt-0.5">{group.hint}</p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => toggleGroup(group, !allOn)}
                  className="text-[11px] text-muted-foreground hover:text-foreground underline shrink-0"
                >
                  {allOn ? "none" : "all"}
                </button>
              </div>
              <div className="space-y-1">
                {group.tools.map((t) => (
                  <label
                    key={t.name}
                    className="flex items-center gap-2 text-xs cursor-pointer rounded px-1 py-0.5 hover:bg-muted/50"
                  >
                    <input
                      type="checkbox"
                      checked={enabled.has(t.name)}
                      onChange={() => toggle(t.name)}
                      className="h-3.5 w-3.5 accent-primary"
                    />
                    <span className={enabled.has(t.name) ? "" : "text-muted-foreground"}>
                      {t.label}
                    </span>
                    <span className="ml-auto font-mono text-[10px] text-muted-foreground/60">
                      {t.name}
                    </span>
                  </label>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
