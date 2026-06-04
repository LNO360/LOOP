"use client"
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  useSensor,
  useSensors,
  useDroppable,
  useDraggable,
} from "@dnd-kit/core"
import { TaskCard } from "./task-card"
import { cn } from "@/lib/utils"
import { useState } from "react"

export const COLUMNS = [
  { id: "todo",        label: "To Do",       dot: "bg-slate-400" },
  { id: "in_progress", label: "In Progress",  dot: "bg-blue-400"  },
  { id: "done",        label: "Done",         dot: "bg-emerald-400" },
  { id: "cancelled",   label: "Cancelled",    dot: "bg-rose-400"  },
]

export interface Task {
  id: string
  title: string
  description?: string
  priority: string
  status: string
  due_date?: string | null
  assignee_id?: string | null
  assignee_ids?: string[]
  assignee_names?: string[]
  project_id?: string | null
  tags?: string[]
}

/* ── Droppable column wrapper ─────────────────────────────────────────── */
function DroppableColumn({
  col,
  tasks,
  memberMap,
  projectMap,
  onTaskClick,
  activeId,
}: {
  col: (typeof COLUMNS)[0]
  tasks: Task[]
  memberMap: Record<string, string>
  projectMap?: Record<string, string>
  onTaskClick: (task: Task) => void
  activeId: string | null
}) {
  const { setNodeRef, isOver } = useDroppable({ id: col.id })

  return (
    <div className="flex-shrink-0 w-[272px] flex flex-col">
      {/* Column header */}
      <div className="flex items-center gap-2 mb-3 px-1">
        <span className={cn("h-2 w-2 rounded-full shrink-0", col.dot)} />
        <span className="text-sm font-semibold">{col.label}</span>
        <span className="ml-auto text-xs font-semibold tabular-nums bg-muted text-muted-foreground rounded-full px-2 py-0.5 min-w-[22px] text-center">
          {tasks.length}
        </span>
      </div>

      {/* Drop target */}
      <div
        ref={setNodeRef}
        className={cn(
          "flex-1 min-h-[480px] rounded-xl p-2 space-y-2 transition-all duration-150 border-2 border-transparent",
          "bg-muted/25",
          isOver && "bg-accent/8 border-accent/40 shadow-[inset_0_0_0_1px_theme(colors.blue.500/20)]"
        )}
      >
        {tasks.map((task) => (
          <DraggableTask
            key={task.id}
            task={task}
            memberMap={memberMap}
            projectName={task.project_id && projectMap ? projectMap[task.project_id] : undefined}
            onTaskClick={onTaskClick}
            anyDragging={activeId !== null}
          />
        ))}

        {tasks.length === 0 && (
          <div
            className={cn(
              "flex items-center justify-center h-16 rounded-lg border-2 border-dashed text-xs transition-colors",
              isOver
                ? "border-accent/60 text-accent"
                : "border-muted-foreground/15 text-muted-foreground/40"
            )}
          >
            {isOver ? "Release to drop" : "No tasks"}
          </div>
        )}
      </div>
    </div>
  )
}

/* ── Draggable task wrapper ───────────────────────────────────────────── */
function DraggableTask({
  task,
  memberMap,
  projectName,
  onTaskClick,
  anyDragging,
}: {
  task: Task
  memberMap: Record<string, string>
  projectName?: string
  onTaskClick: (task: Task) => void
  anyDragging: boolean
}) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: task.id,
  })

  return (
    <div
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      className={cn(
        "touch-none cursor-grab active:cursor-grabbing rounded-lg",
        isDragging && "opacity-0 pointer-events-none"
      )}
    >
      <TaskCard
        task={task}
        onClick={() => { if (!anyDragging) onTaskClick(task) }}
        memberMap={memberMap}
        projectName={projectName}
      />
    </div>
  )
}

/* ── Board ────────────────────────────────────────────────────────────── */
interface KanbanBoardProps {
  tasks: Task[]
  memberMap: Record<string, string>
  projectMap?: Record<string, string>
  onTaskClick: (task: Task) => void
  onStatusChange: (taskId: string, status: string) => void
}

export function KanbanBoard({
  tasks,
  memberMap,
  projectMap,
  onTaskClick,
  onStatusChange,
}: KanbanBoardProps) {
  const [activeId, setActiveId] = useState<string | null>(null)
  const activeTask = tasks.find((t) => t.id === activeId)

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } })
  )

  function handleDragStart({ active }: DragStartEvent) {
    setActiveId(String(active.id))
  }

  function handleDragEnd({ active, over }: DragEndEvent) {
    setActiveId(null)
    if (!over) return

    const activeTaskId = String(active.id)
    const overId = String(over.id)

    // Dropped directly on a column background
    const targetCol = COLUMNS.find((c) => c.id === overId)
    if (targetCol) {
      const currentTask = tasks.find((t) => t.id === activeTaskId)
      if (currentTask && currentTask.status !== targetCol.id) {
        onStatusChange(activeTaskId, targetCol.id)
      }
      return
    }

    // Dropped on another task → move to that task's column
    const targetTask = tasks.find((t) => t.id === overId)
    if (targetTask && targetTask.id !== activeTaskId) {
      const currentTask = tasks.find((t) => t.id === activeTaskId)
      if (currentTask && currentTask.status !== targetTask.status) {
        onStatusChange(activeTaskId, targetTask.status)
      }
    }
  }

  return (
    <DndContext
      sensors={sensors}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
    >
      <div className="flex gap-4 overflow-x-auto pb-4 pr-2 h-full">
        {COLUMNS.map((col) => (
          <DroppableColumn
            key={col.id}
            col={col}
            tasks={tasks.filter((t) => t.status === col.id)}
            memberMap={memberMap}
            projectMap={projectMap}
            onTaskClick={onTaskClick}
            activeId={activeId}
          />
        ))}
      </div>

      {/* Ghost card that follows the cursor */}
      <DragOverlay dropAnimation={null}>
        {activeTask && (
          <div className="rotate-1 scale-105 shadow-2xl opacity-90 w-[272px]">
            <TaskCard
              task={activeTask}
              onClick={() => {}}
              memberMap={memberMap}
            />
          </div>
        )}
      </DragOverlay>
    </DndContext>
  )
}
