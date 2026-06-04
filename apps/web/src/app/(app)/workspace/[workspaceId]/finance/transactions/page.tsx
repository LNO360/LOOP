"use client"
import { use, useState } from "react"
import { format } from "date-fns"
import { Plus, TrendingUp, TrendingDown, Pencil, Trash2, X, Check } from "lucide-react"
import {
  useFinanceTransactions, useFinanceAccounts, useFinanceCategories,
  useCreateTransaction, useUpdateTransaction, useDeleteTransaction,
  formatMoney, FinanceTransaction,
} from "@/hooks/use-finance"
import { cn } from "@/lib/utils"

function Badge({ children, variant = "default" }: { children: React.ReactNode; variant?: "income" | "expense" | "default" }) {
  return (
    <span className={cn(
      "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
      variant === "income" ? "bg-emerald-50 text-emerald-700" :
      variant === "expense" ? "bg-rose-50 text-rose-700" :
      "bg-slate-100 text-slate-700"
    )}>{children}</span>
  )
}

function TransactionForm({
  accounts,
  categories,
  initial,
  onSave,
  onCancel,
  loading,
}: {
  accounts: Array<{ id: string; name: string }>
  categories: Array<{ id: string; name: string; kind: string }>
  initial?: Partial<FinanceTransaction>
  onSave: (data: Record<string, unknown>) => void
  onCancel: () => void
  loading: boolean
}) {
  const [form, setForm] = useState({
    account_id: initial?.account_id ?? accounts[0]?.id ?? "",
    direction: initial?.direction ?? "expense",
    amount_cents: initial?.amount_cents ? (initial.amount_cents / 100).toString() : "",
    occurred_on: initial?.occurred_on ?? new Date().toISOString().slice(0, 10),
    description: initial?.description ?? "",
    currency: initial?.currency ?? "INR",
    category_id: initial?.category_id ?? "",
    reference: initial?.reference ?? "",
  })

  const filteredCats = categories.filter(c => c.kind === form.direction)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSave({
      ...form,
      amount_cents: Math.round(parseFloat(form.amount_cents) * 100),
      category_id: form.category_id || undefined,
      reference: form.reference || undefined,
    })
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3 rounded-xl border border-border/60 bg-white p-4">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs font-medium text-muted-foreground">Direction</label>
          <select
            className="mt-1 w-full rounded-lg border border-border/60 px-3 py-2 text-sm"
            value={form.direction}
            onChange={e => setForm(f => ({ ...f, direction: e.target.value as "income" | "expense", category_id: "" }))}
          >
            <option value="income">Income</option>
            <option value="expense">Expense</option>
          </select>
        </div>
        <div>
          <label className="text-xs font-medium text-muted-foreground">Amount (INR)</label>
          <input
            type="number"
            step="0.01"
            min="0"
            required
            className="mt-1 w-full rounded-lg border border-border/60 px-3 py-2 text-sm"
            placeholder="0.00"
            value={form.amount_cents}
            onChange={e => setForm(f => ({ ...f, amount_cents: e.target.value }))}
          />
        </div>
        <div>
          <label className="text-xs font-medium text-muted-foreground">Date</label>
          <input
            type="date"
            required
            className="mt-1 w-full rounded-lg border border-border/60 px-3 py-2 text-sm"
            value={form.occurred_on}
            onChange={e => setForm(f => ({ ...f, occurred_on: e.target.value }))}
          />
        </div>
        <div>
          <label className="text-xs font-medium text-muted-foreground">Account</label>
          <select
            className="mt-1 w-full rounded-lg border border-border/60 px-3 py-2 text-sm"
            value={form.account_id}
            onChange={e => setForm(f => ({ ...f, account_id: e.target.value }))}
          >
            {accounts.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
        </div>
        <div className="col-span-2">
          <label className="text-xs font-medium text-muted-foreground">Description</label>
          <input
            required
            className="mt-1 w-full rounded-lg border border-border/60 px-3 py-2 text-sm"
            placeholder="e.g. AWS subscription, Client payment..."
            value={form.description}
            onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
          />
        </div>
        <div>
          <label className="text-xs font-medium text-muted-foreground">Category</label>
          <select
            className="mt-1 w-full rounded-lg border border-border/60 px-3 py-2 text-sm"
            value={form.category_id}
            onChange={e => setForm(f => ({ ...f, category_id: e.target.value }))}
          >
            <option value="">— none —</option>
            {filteredCats.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs font-medium text-muted-foreground">Reference</label>
          <input
            className="mt-1 w-full rounded-lg border border-border/60 px-3 py-2 text-sm"
            placeholder="Invoice #, UTR..."
            value={form.reference}
            onChange={e => setForm(f => ({ ...f, reference: e.target.value }))}
          />
        </div>
      </div>
      <div className="flex gap-2 justify-end pt-1">
        <button type="button" onClick={onCancel} className="flex items-center gap-1 rounded-lg border border-border/60 px-3 py-1.5 text-sm hover:bg-slate-50">
          <X size={13} /> Cancel
        </button>
        <button type="submit" disabled={loading} className="flex items-center gap-1 rounded-lg bg-foreground text-background px-3 py-1.5 text-sm disabled:opacity-50">
          <Check size={13} /> {loading ? "Saving…" : "Save"}
        </button>
      </div>
    </form>
  )
}

export default function TransactionsPage({ params }: { params: Promise<{ workspaceId: string }> }) {
  const { workspaceId } = use(params)
  const [showForm, setShowForm] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)
  const [filterDir, setFilterDir] = useState<string>("")
  const [filterFrom, setFilterFrom] = useState("")
  const [filterTo, setFilterTo] = useState("")

  const { data: transactions = [], isLoading } = useFinanceTransactions(workspaceId, {
    direction: filterDir || undefined,
    from_date: filterFrom || undefined,
    to_date: filterTo || undefined,
    limit: 200,
  })
  const { data: accounts = [] } = useFinanceAccounts(workspaceId)
  const { data: categories = [] } = useFinanceCategories(workspaceId)

  const createTx = useCreateTransaction(workspaceId)
  const updateTx = useUpdateTransaction(workspaceId)
  const deleteTx = useDeleteTransaction(workspaceId)

  const accountMap = Object.fromEntries(accounts.map(a => [a.id, a.name]))
  const catMap = Object.fromEntries(categories.map(c => [c.id, c.name]))

  return (
    <div className="p-6 space-y-4 max-w-5xl">
      {/* Header + filters */}
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-sm font-semibold flex-1">Transactions</h2>
        <input type="date" value={filterFrom} onChange={e => setFilterFrom(e.target.value)}
          className="rounded-lg border border-border/60 px-2 py-1.5 text-xs" placeholder="From" />
        <input type="date" value={filterTo} onChange={e => setFilterTo(e.target.value)}
          className="rounded-lg border border-border/60 px-2 py-1.5 text-xs" placeholder="To" />
        <select value={filterDir} onChange={e => setFilterDir(e.target.value)}
          className="rounded-lg border border-border/60 px-2 py-1.5 text-xs">
          <option value="">All</option>
          <option value="income">Income</option>
          <option value="expense">Expense</option>
        </select>
        <button
          onClick={() => { setShowForm(true); setEditId(null) }}
          className="flex items-center gap-1.5 rounded-xl bg-foreground text-background px-3 py-1.5 text-sm font-medium"
        >
          <Plus size={14} /> Add
        </button>
      </div>

      {/* Add form */}
      {showForm && !editId && (
        <TransactionForm
          accounts={accounts}
          categories={categories}
          onSave={(data) => createTx.mutate(data as Parameters<typeof createTx.mutate>[0], { onSuccess: () => setShowForm(false) })}
          onCancel={() => setShowForm(false)}
          loading={createTx.isPending}
        />
      )}

      {/* Table */}
      {isLoading ? (
        <div className="text-sm text-muted-foreground py-8 text-center">Loading…</div>
      ) : transactions.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border/60 py-16 text-center">
          <p className="text-muted-foreground text-sm">No transactions found</p>
        </div>
      ) : (
        <div className="rounded-xl border border-border/60 bg-white overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-border/60 bg-slate-50/60">
              <tr>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground">Date</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground">Description</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground">Category</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground">Account</th>
                <th className="text-right px-4 py-2.5 text-xs font-medium text-muted-foreground">Amount</th>
                <th className="w-16" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40">
              {transactions.map(tx => (
                <tr key={tx.id}>
                  {editId === tx.id ? (
                    <td colSpan={6} className="px-4 py-2">
                      <TransactionForm
                        accounts={accounts}
                        categories={categories}
                        initial={tx}
                        onSave={(data) => updateTx.mutate({ id: tx.id, ...data }, { onSuccess: () => setEditId(null) })}
                        onCancel={() => setEditId(null)}
                        loading={updateTx.isPending}
                      />
                    </td>
                  ) : (
                    <>
                      <td className="px-4 py-2.5 text-xs text-muted-foreground whitespace-nowrap">
                        {format(new Date(tx.occurred_on), "dd MMM yyyy")}
                      </td>
                      <td className="px-4 py-2.5 max-w-[200px] truncate">{tx.description}</td>
                      <td className="px-4 py-2.5">
                        {tx.category_id ? (
                          <Badge>{catMap[tx.category_id] ?? "—"}</Badge>
                        ) : <span className="text-muted-foreground">—</span>}
                      </td>
                      <td className="px-4 py-2.5 text-xs text-muted-foreground">{accountMap[tx.account_id] ?? "—"}</td>
                      <td className="px-4 py-2.5 text-right font-medium">
                        <span className={tx.direction === "income" ? "text-emerald-600" : "text-rose-600"}>
                          {tx.direction === "income" ? "+" : "−"}
                          {formatMoney(tx.amount_cents, tx.currency)}
                        </span>
                      </td>
                      <td className="px-4 py-2.5">
                        <div className="flex items-center justify-end gap-1">
                          <button onClick={() => setEditId(tx.id)} className="p-1 rounded hover:bg-slate-100 text-muted-foreground hover:text-foreground">
                            <Pencil size={12} />
                          </button>
                          <button
                            onClick={() => { if (confirm("Delete this transaction?")) deleteTx.mutate(tx.id) }}
                            className="p-1 rounded hover:bg-rose-50 text-muted-foreground hover:text-rose-600"
                          >
                            <Trash2 size={12} />
                          </button>
                        </div>
                      </td>
                    </>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
