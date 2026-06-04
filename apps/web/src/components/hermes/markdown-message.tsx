"use client"
/**
 * Renders an AI response with markdown support.
 * Uses react-markdown + remark-gfm for full GFM (tables, strikethrough, task lists).
 */
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { cn } from "@/lib/utils"

interface MarkdownMessageProps {
  content: string
  className?: string
}

export function MarkdownMessage({ content, className }: MarkdownMessageProps) {
  return (
    <div className={cn("prose-reset", className)}>
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        // Paragraphs
        p: ({ children }) => (
          <p className="mb-3 last:mb-0 leading-7">{children}</p>
        ),
        // Headings
        h1: ({ children }) => (
          <h1 className="mb-3 mt-5 text-lg font-bold first:mt-0">{children}</h1>
        ),
        h2: ({ children }) => (
          <h2 className="mb-2 mt-4 text-base font-semibold first:mt-0">{children}</h2>
        ),
        h3: ({ children }) => (
          <h3 className="mb-2 mt-3 text-sm font-semibold first:mt-0">{children}</h3>
        ),
        // Lists
        ul: ({ children }) => (
          <ul className="mb-3 space-y-1 pl-4">{children}</ul>
        ),
        ol: ({ children }) => (
          <ol className="mb-3 space-y-1 pl-4 list-decimal">{children}</ol>
        ),
        li: ({ children }) => (
          <li className="leading-6 text-[15px] before:mr-2 before:content-['–'] before:text-muted-foreground/60">
            {children}
          </li>
        ),
        // Inline code
        code: ({ children, className: cls }) => {
          const isBlock = cls?.includes("language-")
          if (isBlock) return <code className={cls}>{children}</code>
          return (
            <code className="rounded-md bg-muted px-1.5 py-0.5 font-mono text-[13px] text-foreground">
              {children}
            </code>
          )
        },
        // Code block
        pre: ({ children }) => (
          <pre className="mb-3 overflow-x-auto rounded-xl border border-border/60 bg-[#0f1117] p-4 text-[13px] leading-6 text-slate-200">
            {children}
          </pre>
        ),
        // Blockquote
        blockquote: ({ children }) => (
          <blockquote className="mb-3 border-l-2 border-indigo-300 pl-4 text-muted-foreground italic">
            {children}
          </blockquote>
        ),
        // Bold / italic
        strong: ({ children }) => (
          <strong className="font-semibold text-foreground">{children}</strong>
        ),
        em: ({ children }) => (
          <em className="italic text-foreground/90">{children}</em>
        ),
        // Horizontal rule
        hr: () => <hr className="my-4 border-border/50" />,
        // Tables (GFM)
        table: ({ children }) => (
          <div className="mb-3 overflow-x-auto rounded-xl border border-border/60">
            <table className="min-w-full text-sm">{children}</table>
          </div>
        ),
        thead: ({ children }) => (
          <thead className="bg-muted/50 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {children}
          </thead>
        ),
        tbody: ({ children }) => <tbody className="divide-y divide-border/40">{children}</tbody>,
        tr: ({ children }) => <tr className="hover:bg-muted/20">{children}</tr>,
        th: ({ children }) => <th className="px-4 py-2.5 text-left">{children}</th>,
        td: ({ children }) => <td className="px-4 py-2.5">{children}</td>,
        // Links
        a: ({ href, children }) => (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="text-indigo-600 underline decoration-indigo-300 underline-offset-2 hover:text-indigo-800"
          >
            {children}
          </a>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
    </div>
  )
}
