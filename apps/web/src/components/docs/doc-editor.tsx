"use client"
import { useEditor, EditorContent } from "@tiptap/react"
import StarterKit from "@tiptap/starter-kit"
import Placeholder from "@tiptap/extension-placeholder"
import { useEffect } from "react"
import { cn } from "@/lib/utils"

interface DocEditorProps {
  content?: unknown
  onChange?: (json: unknown) => void
  editable?: boolean
  className?: string
}

export function DocEditor({
  content,
  onChange,
  editable = true,
  className,
}: DocEditorProps) {
  const editor = useEditor({
    extensions: [
      StarterKit,
      Placeholder.configure({ placeholder: "Start writing…" }),
    ],
    content: (content as string) ?? "",
    editable,
    onUpdate: ({ editor }) => {
      onChange?.(editor.getJSON())
    },
  })

  useEffect(() => {
    if (editor && content) {
      editor.commands.setContent(content as string)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editor])

  return (
    <EditorContent
      editor={editor}
      className={cn(
        "prose dark:prose-invert max-w-none text-sm focus:outline-none",
        "[&_.ProseMirror]:min-h-[300px] [&_.ProseMirror]:outline-none",
        "[&_.ProseMirror_p.is-editor-empty:first-child::before]:content-[attr(data-placeholder)]",
        "[&_.ProseMirror_p.is-editor-empty:first-child::before]:text-muted-foreground",
        "[&_.ProseMirror_p.is-editor-empty:first-child::before]:pointer-events-none",
        "[&_.ProseMirror_p.is-editor-empty:first-child::before]:float-left",
        className
      )}
    />
  )
}
