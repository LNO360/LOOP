"use client"
import { use } from "react"
import Link from "next/link"
import { TrendingUp, TrendingDown, Wallet, FileWarning, Plus, ArrowRightLeft } from "lucide-react"
import { useFinanceOverview, useFinanceAccounts, formatMoney } from "@/hooks/use-finance"
import { cn } from "@/lib/utils"

interface OverviewCardProps {
  label: string
  value: string
  subtext?: string
  icon: React.ElementType
  positive?: boolean
  negative?: boolean
}

function OverviewCard({ label, value, subtext, icon: Icon, positive, negative }: OverviewCardProps) {
  return (
    <div className="rounded-2xl border border-border/60 bg-card p-5 shadow-sm flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{label}</p>
        <div className={cn(
          "flex h-8 w-8 items-center justify-center rounded-xl",
          positive ? "bg-emerald-500/10 text-emerald-500" :
          negative ? "bg-rose-500/10 text-rose-500" :
          "bg-muted text-muted-foreground"
        )}>
          <Icon size={16} />
        </div>
      </div>
      <p className={cn(
        "text-2xl font-bold tracking-tight",
        positive ? "text-emerald-600" :
        negative ? "text-rose-600" :
        "text-foreground"
      )}>{value}</p>
      {subtext && <p className="text-xs text-muted-foreground">{subtext}</p>}
    </div>
  )
}

export default function FinanceOverviewPage({ params }: { params: Promise<{ workspaceId: string }> }) {
  const { workspaceId } = use(params)
  const { data: overview, isLoading } = useFinanceOverview(workspaceId)
  const { data: accounts = [] } = useFinanceAccounts(workspaceId)

  const net = overview?.mtd_net_cents ?? 0

  return (
    <div className="p-6 space-y-6 max-w-5xl">
      {/* Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        <OverviewCard
          label="Cash Position"
          value={isLoading ? "…" : formatMoney(overview?.cash_position_cents ?? 0)}
          subtext="All cash + bank accounts"
          icon={Wallet}
        />
        <OverviewCard
          label="MTD Revenue"
          value={isLoading ? "…" : formatMoney(overview?.mtd_revenue_cents ?? 0)}
          subtext="Month to date income"
          icon={TrendingUp}
          positive
        />
        <OverviewCard
          label="MTD Expenses"
          value={isLoading ? "…" : formatMoney(overview?.mtd_expense_cents ?? 0)}
          subtext="Month to date spend"
          icon={TrendingDown}
          negative
        />
        <OverviewCard
          label="MTD Net"
          value={isLoading ? "…" : formatMoney(net)}
          subtext={net >= 0 ? "Profitable month" : "Deficit month"}
          icon={net >= 0 ? TrendingUp : TrendingDown}
          positive={net > 0}
          negative={net < 0}
        />
        <OverviewCard
          label="Unpaid Invoices"
          value={isLoading ? "…" : `${overview?.unpaid_invoices_count ?? 0}`}
          subtext={isLoading ? "" : formatMoney(overview?.unpaid_invoices_total_cents ?? 0) + " outstanding"}
          icon={FileWarning}
          negative={(overview?.unpaid_invoices_count ?? 0) > 0}
        />
      </div>

      {/* Quick actions */}
      <div className="flex gap-3">
        <Link
          href={`/workspace/${workspaceId}/finance/transactions`}
          className="flex items-center gap-2 rounded-xl border border-border/60 bg-card px-4 py-2.5 text-sm font-medium hover:bg-muted transition-colors"
        >
          <Plus size={15} />
          Add Transaction
        </Link>
        <Link
          href={`/workspace/${workspaceId}/finance/invoices`}
          className="flex items-center gap-2 rounded-xl border border-border/60 bg-card px-4 py-2.5 text-sm font-medium hover:bg-muted transition-colors"
        >
          <Plus size={15} />
          New Invoice
        </Link>
      </div>

      {/* Accounts list */}
      {accounts.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold mb-3">Accounts</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {accounts.filter(a => a.is_active).map(acc => (
              <div key={acc.id} className="rounded-xl border border-border/60 bg-card px-4 py-3 flex justify-between items-center">
                <div>
                  <p className="text-sm font-medium">{acc.name}</p>
                  <p className="text-xs text-muted-foreground capitalize">{acc.type}</p>
                </div>
                <p className={cn(
                  "text-sm font-semibold",
                  acc.balance_cents >= 0 ? "text-emerald-600" : "text-rose-600"
                )}>
                  {formatMoney(acc.balance_cents)}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && accounts.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border/60 py-16 text-center">
          <Wallet size={36} className="mb-3 text-muted-foreground/40" />
          <p className="font-medium text-muted-foreground">No accounts yet</p>
          <p className="text-sm text-muted-foreground/70 mt-1 mb-4">Add a cash or bank account to start tracking</p>
          <Link
            href={`/workspace/${workspaceId}/finance/settings`}
            className="flex items-center gap-2 rounded-xl bg-foreground text-background px-4 py-2 text-sm font-medium"
          >
            <Plus size={14} />
            Add Account
          </Link>
        </div>
      )}
    </div>
  )
}
