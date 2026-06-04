"use client"
import { use } from "react"
import { useMessages, useSendMessage } from "@/hooks/use-messages"
import { MessageFeed } from "@/components/messaging/message-feed"
import { MessageComposer } from "@/components/messaging/message-composer"
import { useQuery } from "@tanstack/react-query"
import { useAuthStore } from "@/store/auth"
import { api } from "@/lib/api"
import { MessageCircle } from "lucide-react"

interface MemberInfo {
  id: string
  name: string
}

export default function DMPage({
  params,
}: {
  params: Promise<{ workspaceId: string; channelId: string }>
}) {
  const { workspaceId, channelId } = use(params)
  const currentUser = useAuthStore((s) => s.user)
  const currentUserId = currentUser?.id ?? ""

  const { data: messages = [], isLoading } = useMessages(workspaceId, channelId)
  const { mutate: sendMessage } = useSendMessage(workspaceId, channelId)

  const { data: dms = [] } = useQuery({
    queryKey: ["dms", workspaceId],
    queryFn: () => api.get(`/workspaces/${workspaceId}/dms`).then((r) => r.data),
    staleTime: 60_000,
  })
  const thisDM = (dms as Array<{ id: string; other_user_name?: string }>).find((d) => d.id === channelId)
  const otherName = thisDM?.other_user_name ?? "Direct Message"

  const { data: members = [] } = useQuery({
    queryKey: ["members", workspaceId],
    queryFn: () => api.get(`/workspaces/${workspaceId}/members`).then((r) => r.data as MemberInfo[]),
    staleTime: 60_000,
  })
  const memberMap = Object.fromEntries(members.map((m) => [m.id, m.name]))

  return (
    <div className="flex flex-col h-full">
      <div className="h-14 border-b flex items-center gap-2 px-4 shrink-0">
        <MessageCircle size={16} className="text-muted-foreground" />
        <span className="font-medium text-sm">{otherName}</span>
      </div>
      <MessageFeed
        messages={messages}
        isLoading={isLoading}
        members={memberMap}
        currentUserId={currentUserId}
        channelId={channelId}
        onThreadClick={() => {}}
        onCreateTask={() => {}}
      />
      <MessageComposer
        placeholder={`Message ${otherName}…`}
        onSend={(content) => sendMessage({ content })}
        workspaceId={workspaceId}
        members={members}
      />
    </div>
  )
}
