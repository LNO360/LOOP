"use client"

import { useState } from "react"
import { AlertTriangle, Bot, FileText, Plug2, Save, Settings2, UserCircle2, Wrench } from "lucide-react"
import { ModelPicker } from "@/components/hermes/model-picker"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  useHermesConfig,
  useMemoryMd,
  useSoulMd,
  useUserProfile,
  type HermesFileResult,
} from "@/hooks/use-hermes"
import { IntegrationsTab } from "@/components/hermes/integrations-tab"
import { ToolsTab } from "@/components/hermes/tools-tab"

type EditorTab = "soul" | "memory" | "profile" | "tools" | "config" | "integrations"

/** Read a flat top-level YAML key: `model: "value"` */
function getFlatConfigValue(content: string, key: string): string {
  for (const line of content.split(/\r?\n/)) {
    const match = line.match(new RegExp(`^\\s*${key}:\\s*(.+)\\s*$`))
    if (match) {
      let value = match[1].trim()
      if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
        value = value.slice(1, -1)
      }
      return value
    }
  }
  return ""
}

/** Set a flat top-level YAML key; add if missing. */
function setFlatConfigValue(content: string, key: string, value: string): string {
  const lines = content.split(/\r?\n/)
  const quoted = `"${value.replaceAll('"', '\\"')}"`
  const newLine = `${key}: ${quoted}`
  const idx = lines.findIndex(l => new RegExp(`^\\s*${key}:`).test(l))
  if (idx >= 0) {
    lines[idx] = newLine
    return lines.join("\n")
  }
  return `${content.trimEnd()}\n${newLine}\n`
}

interface AgentSettingsTabProps {
  workspaceId: string
}

function getNestedConfigValue(content: string, section: string, key: string): string {
  const lines = content.split(/\r?\n/)
  let inSection = false
  let sectionIndent = 0

  for (const line of lines) {
    const sectionMatch = line.match(/^(\s*)([^:#]+):\s*$/)
    if (sectionMatch) {
      const indent = sectionMatch[1].length
      const name = sectionMatch[2].trim()
      if (name === section) {
        inSection = true
        sectionIndent = indent
        continue
      }
      if (inSection && indent <= sectionIndent) {
        break
      }
    }

    if (!inSection) continue

    const keyMatch = line.match(/^(\s*)([^:#]+):\s*(.*)\s*$/)
    if (!keyMatch) continue

    const indent = keyMatch[1].length
    const name = keyMatch[2].trim()
    let value = keyMatch[3].trim()

    if (indent <= sectionIndent || name !== key) continue

    if ((value.startsWith("\"") && value.endsWith("\"")) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1)
    }
    return value
  }

  return ""
}

function setNestedConfigValue(content: string, section: string, key: string, value: string): string {
  const lines = content.split(/\r?\n/)
  let sectionIndex = -1
  let sectionIndent = 0
  let insertIndex = lines.length
  let keyIndex = -1

  for (let i = 0; i < lines.length; i += 1) {
    const sectionMatch = lines[i].match(/^(\s*)([^:#]+):\s*$/)
    if (!sectionMatch) continue

    const indent = sectionMatch[1].length
    const name = sectionMatch[2].trim()

    if (sectionIndex === -1) {
      if (name === section) {
        sectionIndex = i
        sectionIndent = indent
        insertIndex = i + 1
      }
      continue
    }

    if (indent <= sectionIndent) {
      insertIndex = i
      break
    }

    const keyMatch = lines[i].match(/^(\s*)([^:#]+):\s*(.*)\s*$/)
    if (!keyMatch) continue

    const keyIndent = keyMatch[1].length
    const keyName = keyMatch[2].trim()
    if (keyIndent > sectionIndent && keyName === key) {
      keyIndex = i
    }
  }

  const renderedLine = `${" ".repeat(sectionIndent + 2)}${key}: "${value.replaceAll("\"", "\\\"")}"`

  if (sectionIndex === -1) {
    const prefix = content.trimEnd()
    return `${prefix}${prefix ? "\n\n" : ""}${section}:\n  ${key}: "${value.replaceAll("\"", "\\\"")}"\n`
  }

  if (keyIndex >= 0) {
    lines[keyIndex] = renderedLine
  } else {
    lines.splice(insertIndex, 0, renderedLine)
  }

  return `${lines.join("\n")}\n`
}

function EditorPane({
  title,
  description,
  initialValue,
  onSave,
  isLoading,
  isSaving,
  saveError,
  warning,
}: {
  title: string
  description: string
  initialValue: string
  onSave: (value: string) => Promise<void>
  isLoading: boolean
  isSaving: boolean
  saveError: string | null
  warning?: string
}) {
  const [draft, setDraft] = useState(initialValue)

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold">{title}</h3>
          <p className="text-xs text-muted-foreground mt-1">{description}</p>
        </div>
        <Button size="sm" onClick={() => onSave(draft)} disabled={isLoading || isSaving}>
          <Save size={14} className="mr-1.5" />
          {isSaving ? "Saving..." : "Save"}
        </Button>
      </div>

      {warning && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
          <AlertTriangle size={14} className="inline mr-1.5 align-text-bottom" />
          {warning}
        </div>
      )}

      <textarea
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        className="min-h-[380px] w-full rounded-xl border bg-background px-4 py-3 font-mono text-xs leading-6 outline-none focus:ring-1 focus:ring-ring"
        spellCheck={false}
        disabled={isLoading}
      />

      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
        <span>{draft.length.toLocaleString()} characters</span>
        <span>
          {saveError ? `Save failed: ${saveError}` : isLoading ? "Loading..." : "Ready"}
        </span>
      </div>
    </div>
  )
}

function EngineSettingsCard({
  configContent,
  configHook,
}: {
  configContent: string
  configHook: HermesFileResult
}) {
  // Hermes config.yaml uses flat `model: "provider:model-id"` string
  const [engineModel, setEngineModel] = useState(
    getFlatConfigValue(configContent, "model")
  )
  const [engineMessage, setEngineMessage] = useState<string | null>(null)
  const provider = getFlatConfigValue(configContent, "model").split("/")[0]?.split(":")[0] || "openrouter"
  const configDefaultModel = getFlatConfigValue(configContent, "model")

  async function saveEngineModel() {
    if (!engineModel.trim()) return

    const nextConfig = setFlatConfigValue(configContent, "model", engineModel.trim())

    try {
      await configHook.save(nextConfig)
      setEngineMessage("Default model updated.")
    } catch {
      setEngineMessage("Could not update the default model.")
    }
  }

  return (
    <div className="rounded-2xl border bg-card p-5 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold">Engine</h2>
          <p className="text-xs text-muted-foreground mt-1">
            Hermes stays underneath as the runtime. This is where we decide how AI work is routed in the workspace.
          </p>
        </div>
        <div className="rounded-full bg-muted px-3 py-1 text-[11px] font-medium text-muted-foreground">
          Powered by Hermes
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_220px]">
        <div className="space-y-2">
          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            Default model
          </label>
          <ModelPicker
            value={engineModel}
            onChange={setEngineModel}
            defaultOptionLabel="Choose a default model"
          />
          <p className="text-xs text-muted-foreground">
            Used for general chat and any agent that does not explicitly override its model.
          </p>
        </div>

        <div className="rounded-xl border bg-muted/30 px-4 py-3">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            Provider
          </p>
          <p className="mt-2 text-sm font-medium">{provider || "openrouter"}</p>
          <p className="mt-2 text-xs text-muted-foreground">
            Provider routing still lives in the Hermes engine config, but it is managed from this workspace now.
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-muted-foreground">
          Current default: <span className="font-mono">{configDefaultModel || "not set"}</span>
        </p>
        <div className="flex items-center gap-3">
          {engineMessage && (
            <span className="text-xs text-muted-foreground">{engineMessage}</span>
          )}
          <Button
            size="sm"
            onClick={saveEngineModel}
            disabled={configHook.isSaving || !engineModel.trim() || engineModel.trim() === configDefaultModel}
          >
            {configHook.isSaving ? "Saving..." : "Save default model"}
          </Button>
        </div>
      </div>
    </div>
  )
}

export function AgentSettingsTab({ workspaceId }: AgentSettingsTabProps) {
  const soul = useSoulMd(workspaceId)
  const memory = useMemoryMd(workspaceId)
  const profile = useUserProfile(workspaceId)
  const config = useHermesConfig(workspaceId)

  const [activeTab, setActiveTab] = useState<EditorTab>("config")

  // editors only covers the text-editor tabs; integrations is rendered separately


  const editors: Record<
    Exclude<EditorTab, "integrations" | "tools">,
    {
      title: string
      description: string
      warning?: string
      hook: HermesFileResult
      icon: typeof Bot
    }
  > = {
    soul: {
      title: "Assistant instructions",
      description: "Core system guidance for the Hermes runtime across the workspace.",
      hook: soul,
      icon: Bot,
    },
    memory: {
      title: "Shared runtime memory",
      description: "Long-lived notes Hermes can recall across future AI work.",
      hook: memory,
      icon: FileText,
    },
    profile: {
      title: "User profile",
      description: "Preferences and working style the assistant should remember about you.",
      hook: profile,
      icon: UserCircle2,
    },
    config: {
      title: "Raw engine config",
      description: "Low-level runtime configuration for provider routing, approvals, and limits.",
      warning: "Invalid YAML can break Hermes the next time the runtime starts.",
      hook: config,
      icon: Settings2,
    },
  }

  return (
    <div className="p-6 max-w-5xl space-y-6">
      <EngineSettingsCard
        key={getFlatConfigValue(config.content, "model")}
        configContent={config.content}
        configHook={config}
      />

      <div className="rounded-2xl border bg-card overflow-hidden">
        <div className="border-b px-5 py-4">
          <h2 className="text-sm font-semibold">AI settings</h2>
          <p className="text-xs text-muted-foreground mt-1">
            Instructions, memory, profile, raw config, and integrations.
          </p>
        </div>

        <Tabs
          value={activeTab}
          onValueChange={(value) => setActiveTab(value as EditorTab)}
          className="p-5"
        >
          <TabsList variant="line" className="mb-5 h-auto w-full flex-wrap justify-start p-0">
            {Object.entries(editors).map(([key, editor]) => {
              const Icon = editor.icon
              return (
                <TabsTrigger key={key} value={key} className="px-3 py-2">
                  <Icon size={14} />
                  {editor.title}
                </TabsTrigger>
              )
            })}
            <TabsTrigger value="tools" className="px-3 py-2">
              <Wrench size={14} />
              Tools
            </TabsTrigger>
            <TabsTrigger value="integrations" className="px-3 py-2">
              <Plug2 size={14} />
              Integrations
            </TabsTrigger>
          </TabsList>

          {Object.entries(editors).map(([key, editor]) => (
            <TabsContent key={key} value={key} className="mt-0">
              <EditorPane
                key={`${key}:${editor.hook.content}`}
                title={editor.title}
                description={editor.description}
                initialValue={editor.hook.content}
                onSave={(value) => editor.hook.save(value)}
                isLoading={editor.hook.isLoading}
                isSaving={editor.hook.isSaving}
                saveError={editor.hook.saveError}
                warning={editor.warning}
              />
            </TabsContent>
          ))}

          <TabsContent value="tools" className="mt-0">
            <ToolsTab key={config.content} configHook={config} />
          </TabsContent>

          <TabsContent value="integrations" className="mt-0 -mx-5 -mb-5">
            <IntegrationsTab workspaceId={workspaceId} />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}
