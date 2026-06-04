"use client"
import { Suspense } from "react"
import { useSearchParams } from "next/navigation"
import { SeoAssistantPanel } from "@/components/seo/seo-assistant-panel"
import { useSeoContext } from "@/components/seo/seo-context"

function AssistantContent() {
  const { workspaceId } = useSeoContext()
  const searchParams = useSearchParams()
  const initialPrompt = searchParams.get("context")

  return (
    <div className="h-[calc(100vh-8rem)]">
      <SeoAssistantPanel
        workspaceId={workspaceId}
        initialPrompt={initialPrompt ?? undefined}
        className="h-full"
      />
    </div>
  )
}

export default function SeoAssistantPage() {
  return (
    <Suspense>
      <AssistantContent />
    </Suspense>
  )
}
