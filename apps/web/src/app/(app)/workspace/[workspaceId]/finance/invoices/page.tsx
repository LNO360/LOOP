"use client"
import { use, useState } from "react"
import { format } from "date-fns"
import { Plus, CheckCircle, Clock, AlertTriangle, X, Check } from "lucide-react"
import {
  useFinanceInvoices, useFinanceAccounts, useCreateInvoice, useUpdateInvoice,
  formatMoney, FinanceInvoice,
} from "@/hooks/use-finance"
import { cn } from "@/lib/utils"

const STATUS_STYLES: Record<string, string> = {
  draft: "bg-slate-100 text-slate-600",
  sent: "bg-blue-50 text-blue-700",
  paid: "bg-emerald-50 text-emerald-700",
  void: "bg-red-50 text-red-600",
}

function InvoiceStatusBadge({ inv }: { inv: FinanceInvoice }) {
  if (inv.overdue && inv.status !== "paid" && inv.status !== "void") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2 py-0.5 text-xs font-medium text-rose-700">
        <AlertTriangle size={10} /> Overdue
      </span>
    )
  }
  return (
    <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium capitalize", STATUS_STYLES[inv.status] ?? "bg-slate-100 text-slate-600")}>
      {inv.status}
    </span>
  )
}

function InvoiceForm({
  onSave,
  onCancel,
  loading,
}: {
  onSave: (data: Record<string, unknown>) => void
  onCancel: () => void
  loading: boolean
}) {
  const [form, setForm] = useState({
    customer_name: "",
    amount: "",
    currency: "INR",
    issued_on: new Date().toISOString().slice(0, 10),
    due_on: "",
    notes: "",
  })
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSave({
      customer_name: form.customer_name,
      amount_cents: Math.round(parseFloat(form.amount) * 100),
      currency: form.currency,
      issued_on: form.issued_on || undefined,
      due_on: form.due_on || undefined,
      notes: form.notes || undefined,
    })
  }
  return (
    <form onSubmit={handleSubmit} className="rounded-xl border border-border/60 bg-white p-4 space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div className="col-span-2">
          <label className="text-xs font-medium text-muted-foreground">Customer Name</label>
          <input required className="mt-1 w-full rounded-lg border border-border/60 px-3 py-2 text-sm"
            value={form.customer_name} onChange={e => setForm(f => ({ ...f, customer_name: e.target.value }))} />
        </div>
        <div>
          <label className="text-xs font-medium text-muted-foreground">Amount (INR)</label>
          <input required type="number" step="0.01" min="0" className="mt-1 w-full rounded-lg border border-border/60 px-3 py-2 text-sm"
            placeholder="0.00" value={form.amount} onChange={e => setForm(f => ({ ...f, amount: e.target.value }))} />
        </div>
        <div>
          <label className="text-xs font-medium text-muted-foreground">Issued On</label>
          <input type="date" className="mt-1 w-full rounded-lg border border-border/60 px-3 py-2 text-sm"
            value={form.issued_on} onChange={e => setForm(f => ({ ...f, issued_on: e.target.value }))} />
        </div>
        <div>
          <label className="text-xs font-medium text-muted-foreground">Due On</label>
          <input type="date" className="mt-1 w-full rounded-lg border border-border/60 px-3 py-2 text-sm"
            value={form.due_on} onChange={e => setForm(f => ({ ...f, due_on: e.target.value }))} />
        </div>
        <div>
          <label className="text-xs font-medium text-muted-foreground">Notes</label>
          <input className="mt-1 w-full rounded-lg border border-border/60 px-3 py-2 text-sm"
            value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} />
        </div>
      </div>
      <div className="flex gap-2 justify-end">
        <button type="button" onClick={onCancel} className="flex items-center gap-1 rounded-lg border border-border/60 px-3 py-1.5 text-sm hover:bg-slate-50">
          <X size={13} /> Cancel
        </button>
        <button type="submit" disabled={loading} className="flex items-center gap-1 rounded-lg bg-foreground text-background px-3 py-1.5 text-sm disabled:opacity-50">
          <Check size={13} /> {loading ? "Saving…" : "Create Invoice"}
        </button>
      </div>
    </form>
  )
}

function MarkPaidDialog({
  inv,
  accounts,
  onConfirm,
  onCancel,
  loading,
}: {
  inv: FinanceInvoice
  accounts: Array<{ id: string; name: string }>
  onConfirm: (data: Record<string, unknown>) => void
  onCancel: () => void
  loading: boolean
}) {
  const [accountId, setAccountId] = useState(accounts[0]?.id ?? "")
  const [paidOn, setPaidOn] = useState(new Date().toISOString().slice(0, 10))
  return (
    <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 space-y-3">
      <p className="text-sm font-medium">Mark <strong>{inv.customer_name}</strong> invoice as paid?</p>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs font-medium text-muted-foreground">Paid On</label>
          <input type="date" value={paidOn} onChange={e => setPaidOn(e.target.value)}
            className="mt-1 w-full rounded-lg border border-border/60 px-3 py-2 text-sm bg-white" />
        </div>
        <div>
          <label className="text-xs font-medium text-muted-foreground">Credit Account (optional)</label>
          <select value={accountId} onChange={e => setAccountId(e.target.value)}
            className="mt-1 w-full rounded-lg border border-border/60 px-3 py-2 text-sm bg-white">
            <option value="">— skip auto-transaction —</option>
            {accounts.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
        </div>
      </div>
      <div className="flex gap-2 justify-end">
        <button onClick={onCancel} className="flex items-center gap-1 rounded-lg border border-border/60 px-3 py-1.5 text-sm bg-white hover:bg-slate-50">
          <X size={13} /> Cancel
        </button>
        <button onClick={() => onConfirm({ status: "paid", paid_on: paidOn, account_id: accountId || undefined })}
          disabled={loading}
          className="flex items-center gap-1 rounded-lg bg-emerald-600 text-white px-3 py-1.5 text-sm disabled:opacity-50">
          <CheckCircle size={13} /> {loading ? "Saving…" : "Mark Paid"}
        </button>
      </div>
    </div>
  )
}

export default function InvoicesPage({ params }: { params: Promise<{ workspaceId: string }> }) {
  const { workspaceId } = use(params)
  const [showForm, setShowForm] = useState(false)
  const [markPaidId, setMarkPaidId] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState("")

  const { data: invoices = [], isLoading } = useFinanceInvoices(workspaceId, statusFilter || undefined)
  const { data: accounts = [] } = useFinanceAccounts(workspaceId)
  const createInv = useCreateInvoice(workspaceId)
  const updateInv = useUpdateInvoice(workspaceId)

  return (
    <div className="p-6 space-y-4 max-w-4xl">
      <div className="flex items-center gap-3">
        <h2 className="text-sm font-semibold flex-1">Invoices</h2>
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
          className="rounded-lg border border-border/60 px-2 py-1.5 text-xs">
          <option value="">All statuses</option>
          <option value="draft">Draft</option>
          <option value="sent">Sent</option>
          <option value="paid">Paid</option>
          <option value="void">Void</option>
        </select>
        <button
          onClick={() => setShowForm(true)}
          className="flex items-center gap-1.5 rounded-xl bg-foreground text-background px-3 py-1.5 text-sm font-medium"
        >
          <Plus size={14} /> New Invoice
        </button>
      </div>

      {showForm && (
        <InvoiceForm
          onSave={(data) => createInv.mutate(data as Parameters<typeof createInv.mutate>[0], { onSuccess: () => setShowForm(false) })}
          onCancel={() => setShowForm(false)}
          loading={createInv.isPending}
        />
      )}

      {isLoading ? (
        <div className="text-sm text-muted-foreground py-8 text-center">Loading…</div>
      ) : invoices.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border/60 py-16 text-center">
          <p className="text-muted-foreground text-sm">No invoices yet</p>
        </div>
      ) : (
        <div className="rounded-xl border border-border/60 bg-white overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-border/60 bg-slate-50/60">
              <tr>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground">Customer</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground">Issued</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground">Due</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground">Status</th>
                <th className="text-right px-4 py-2.5 text-xs font-medium text-muted-foreground">Amount</th>
                <th className="w-24" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40">
              {invoices.map(inv => (
                <>
                  <tr key={inv.id}>
                    <td className="px-4 py-3 font-medium">{inv.customer_name}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {inv.issued_on ? format(new Date(inv.issued_on), "dd MMM yyyy") : "—"}
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {inv.due_on ? format(new Date(inv.due_on), "dd MMM yyyy") : "—"}
                    </td>
                    <td className="px-4 py-3"><InvoiceStatusBadge inv={inv} /></td>
                    <td className="px-4 py-3 text-right font-semibold">
                      {formatMoney(inv.amount_cents, inv.currency)}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-1">
                        {inv.status !== "paid" && inv.status !== "void" && (
                          <button
                            onClick={() => setMarkPaidId(inv.id)}
                            className="flex items-center gap-1 rounded-lg bg-emerald-50 text-emerald-700 hover:bg-emerald-100 px-2 py-1 text-xs font-medium"
                          >
                            <CheckCircle size={11} /> Mark paid
                          </button>
                        )}
                        {inv.status === "draft" && (
                          <button
                            onClick={() => updateInv.mutate({ id: inv.id, status: "sent" })}
                            className="flex items-center gap-1 rounded-lg bg-blue-50 text-blue-700 hover:bg-blue-100 px-2 py-1 text-xs font-medium"
                          >
                            <Clock size={11} /> Send
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                  {markPaidId === inv.id && (
                    <tr key={`${inv.id}-paid`}>
                      <td colSpan={6} className="px-4 py-2">
                        <MarkPaidDialog
                          inv={inv}
                          accounts={accounts}
                          onConfirm={(data) => updateInv.mutate({ id: inv.id, ...data }, { onSuccess: () => setMarkPaidId(null) })}
                          onCancel={() => setMarkPaidId(null)}
                          loading={updateInv.isPending}
                        />
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
