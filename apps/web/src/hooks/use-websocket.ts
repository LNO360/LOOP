"use client"
import { useEffect, useRef, useCallback } from "react"
import { useQueryClient } from "@tanstack/react-query"

export function useWorkspaceSocket(workspaceId: string, channelId: string) {
  const wsRef = useRef<WebSocket | null>(null)
  const retryRef = useRef(0)
  const qc = useQueryClient()

  const connect = useCallback(() => {
    const token = localStorage.getItem("lno_token")
    const url = `${process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000"}/ws/${workspaceId}?token=${token}`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => { retryRef.current = 0 }

    ws.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data)
        if (["message.new", "message.updated", "message.deleted", "reaction.updated"].includes(event.type)) {
          qc.invalidateQueries({ queryKey: ["messages", channelId] })
          qc.invalidateQueries({ queryKey: ["thread"] })
        }
        if (event.type === "notification.new") {
          qc.invalidateQueries({ queryKey: ["notifications"] })
        }
      } catch {}
    }

    ws.onclose = () => {
      const delay = Math.min(1000 * 2 ** retryRef.current, 16000)
      retryRef.current++
      if (retryRef.current <= 5) {
        setTimeout(connect, delay)
      }
    }

    ws.onerror = () => ws.close()
  }, [workspaceId, channelId, qc])

  useEffect(() => {
    connect()
    return () => { wsRef.current?.close(); retryRef.current = 99 } // 99 = stop retrying on unmount
  }, [connect])

  function send(event: object) {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(event))
    }
  }

  return { send }
}
