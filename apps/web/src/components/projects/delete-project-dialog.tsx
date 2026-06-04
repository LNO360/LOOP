"use client"

import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useRouter } from "next/navigation"
import { api } from "@/lib/api"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { AlertTriangle, Loader2 } from "lucide-react"

interface DeleteProjectDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  workspaceId: string
  project: { id: string; name: string }
  taskCount: number
}

export function DeleteProjectDialog({
  open,
  onOpenChange,
  workspaceId,
  project,
  taskCount,
}: DeleteProjectDialogProps) {
  const router = useRouter()
  const qc = useQueryClient()
  const [confirmName, setConfirmName] = useState("")
  const [ackTasks, setAckTasks] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const nameMatches = confirmName.trim() === project.name
  const needsTaskAck = taskCount > 0
  const canDelete = nameMatches && (!needsTaskAck || ackTasks)

  const { mutateAsync: deleteProject, isPending } = useMutation({
    mutationFn: () =>
      api
        .delete(`/workspaces/${workspaceId}/projects/${project.id}`, {
          data: {
            confirm_name: confirmName.trim(),
            acknowledge_tasks: needsTaskAck ? ackTasks : false,
          },
        })
        .then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["projects", workspaceId] })
      qc.invalidateQueries({ queryKey: ["tasks", workspaceId] })
      onOpenChange(false)
      router.push(`/workspace/${workspaceId}/projects`)
    },
  })

  function handleClose(next: boolean) {
    if (!isPending) {
      onOpenChange(next)
      if (!next) {
        setConfirmName("")
        setAckTasks(false)
        setError(null)
      }
    }
  }

  async function handleDelete() {
    if (!canDelete) return
    setError(null)
    try {
      await deleteProject()
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string | { message?: string } } } }
      const detail = ax.response?.data?.detail
      if (typeof detail === "string") setError(detail)
      else if (detail && typeof detail === "object" && "message" in detail)
        setError(String(detail.message))
      else setError("Could not delete project. Please try again.")
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-destructive">
            <AlertTriangle size={18} />
            Delete project
          </DialogTitle>
          <DialogDescription>
            This permanently removes the project <strong>{project.name}</strong>.
            Tasks are not deleted — they are unlinked and stay in your workspace.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 pt-1">
          {needsTaskAck && (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2.5 text-xs text-amber-700 dark:text-amber-400">
              This project has <strong>{taskCount}</strong> linked task
              {taskCount === 1 ? "" : "s"}. Deleting will remove the project link from those
              tasks.
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="confirm-project-name" className="text-xs">
              Type <span className="font-mono font-semibold">{project.name}</span> to confirm
            </Label>
            <Input
              id="confirm-project-name"
              value={confirmName}
              onChange={(e) => setConfirmName(e.target.value)}
              placeholder={project.name}
              autoComplete="off"
              disabled={isPending}
            />
          </div>

          {needsTaskAck && (
            <label className="flex items-start gap-2.5 cursor-pointer text-xs leading-relaxed">
              <input
                type="checkbox"
                checked={ackTasks}
                onChange={(e) => setAckTasks(e.target.checked)}
                disabled={isPending}
                className="mt-0.5 rounded border-border"
              />
              <span>
                I understand {taskCount} task{taskCount === 1 ? "" : "s"} will be unlinked from
                this project (tasks will not be deleted).
              </span>
            </label>
          )}

          {error && (
            <p className="text-xs text-destructive bg-destructive/10 rounded-lg px-3 py-2">
              {error}
            </p>
          )}

          <div className="flex justify-end gap-2 pt-1">
            <Button variant="outline" onClick={() => handleClose(false)} disabled={isPending}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={!canDelete || isPending}
            >
              {isPending ? (
                <>
                  <Loader2 size={14} className="animate-spin mr-1.5" />
                  Deleting…
                </>
              ) : (
                "Delete project"
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
