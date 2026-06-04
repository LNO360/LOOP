import { redirect } from "next/navigation"

/**
 * Redirected to /agents (Actions tab).
 * The full agent control center lives there now.
 */
export default async function AgentActionsPage({
  params,
}: {
  params: Promise<{ workspaceId: string }>
}) {
  const { workspaceId } = await params
  redirect(`/workspace/${workspaceId}/agents?tab=actions`)
}
