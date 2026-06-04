"use client"
import { HermesChatPanel } from "@/components/hermes/hermes-chat-panel"

const SEO_SUGGESTIONS = [
  "Audit my lowest-scoring blog posts and list fixes",
  "Why did impressions drop in the last 28 days?",
  "Suggest meta descriptions for all draft posts",
  "Check if our homepage is indexed in Google",
  "Compare our top queries vs top landing pages",
  "Find blog posts missing meta descriptions or tags",
]

interface SeoAssistantPanelProps {
  workspaceId: string
  initialPrompt?: string
  className?: string
}

export function SeoAssistantPanel({
  workspaceId,
  initialPrompt,
  className,
}: SeoAssistantPanelProps) {
  const initialMessage = initialPrompt
    ? `You are my SEO analyst. Context: ${initialPrompt}. Analyze and suggest specific fixes.`
    : undefined

  return (
    <HermesChatPanel
      workspaceId={workspaceId}
      className={className}
      suggestions={SEO_SUGGESTIONS}
      subtitle="Search Console, blog audit, and web research tools"
      initialMessage={initialMessage}
    />
  )
}
