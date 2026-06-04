import { useState, useCallback } from "react"
import { api } from "@/lib/api"

export interface ChatMessage {
  role: "user" | "assistant"
  content: string
}

export interface AIActionResult {
  tool: string
  args: Record<string, unknown>
  result: { ok?: boolean; error?: string; [key: string]: unknown }
}

export interface AIChatMessage {
  role: "user" | "assistant"
  content: string
  actions?: AIActionResult[]
}

export function useAIChat(workspaceId: string) {
  const [messages, setMessages] = useState<AIChatMessage[]>([])
  const [history, setHistory] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)

  const sendMessage = useCallback(
    async (message: string) => {
      setIsLoading(true)
      setMessages(prev => [...prev, { role: "user", content: message }])

      try {
        const data = await api
          .post(`/workspaces/${workspaceId}/ai/chat`, { message, history })
          .then(r => r.data as { reply: string; actions?: AIActionResult[]; compressed_history?: ChatMessage[] })

        const assistantMsg: AIChatMessage = {
          role: "assistant",
          content: data.reply,
          actions: data.actions,
        }
        setMessages(prev => [...prev, assistantMsg])

        // If server compressed history, fold current turn in too; otherwise append normally
        if (data.compressed_history) {
          setHistory([
            ...data.compressed_history,
            { role: "user", content: message },
            { role: "assistant", content: data.reply },
          ])
        } else {
          setHistory(prev => [
            ...prev,
            { role: "user", content: message },
            { role: "assistant", content: data.reply },
          ])
        }
      } catch {
        // Remove the optimistic user message so the UI doesn't show a dangling bubble
        setMessages(prev => prev.slice(0, -1))
      } finally {
        setIsLoading(false)
      }
    },
    [workspaceId, history]
  )

  const clearHistory = useCallback(() => {
    setMessages([])
    setHistory([])
  }, [])

  return { messages, sendMessage, isLoading, clearHistory }
}

export function useExtractTasks(workspaceId: string) {
  const [isLoading, setIsLoading] = useState(false)
  const extract = useCallback(async (message: string) => {
    setIsLoading(true)
    try {
      return await api
        .post(`/workspaces/${workspaceId}/ai/extract-tasks`, { message })
        .then(r => r.data as { tasks: Array<{ title: string; description?: string; priority: string }> })
    } finally {
      setIsLoading(false)
    }
  }, [workspaceId])
  return { extract, isLoading }
}
