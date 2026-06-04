"use client"
import { use } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import { LayoutDashboard, ArrowRightLeft, FileText, Settings } from "lucide-react"

const tabs = [
  { href: "", label: "Overview", icon: LayoutDashboard },
  { href: "/transactions", label: "Transactions", icon: ArrowRightLeft },
  { href: "/invoices", label: "Invoices", icon: FileText },
  { href: "/settings", label: "Settings", icon: Settings },
]

export default function FinanceLayout({
  children,
  params,
}: {
  children: React.ReactNode
  params: Promise<{ workspaceId: string }>
}) {
  const { workspaceId } = use(params)
  const pathname = usePathname()
  const base = `/workspace/${workspaceId}/finance`

  return (
    <div className="flex flex-col h-full">
      {/* Sub-nav */}
      <div className="border-b border-border/60 bg-background px-6 pt-5 pb-0">
        <div className="flex items-center gap-1 mb-0">
          <h1 className="text-lg font-semibold mr-6">Finance</h1>
          {tabs.map(({ href, label, icon: Icon }) => {
            const fullHref = `${base}${href}`
            const active = href === ""
              ? pathname === base
              : pathname.startsWith(fullHref)
            return (
              <Link
                key={href}
                href={fullHref}
                className={cn(
                  "flex items-center gap-1.5 px-3 py-2 text-sm font-medium border-b-2 transition-colors -mb-px",
                  active
                    ? "border-foreground text-foreground"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                )}
              >
                <Icon size={14} />
                {label}
              </Link>
            )
          })}
        </div>
      </div>
      <div className="flex-1 overflow-auto">
        {children}
      </div>
    </div>
  )
}
