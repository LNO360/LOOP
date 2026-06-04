"use client"
import { use, useState, useRef } from "react"
import { Plus, Upload, CheckCircle2 } from "lucide-react"
import {
  useFinanceSettings, useFinanceAccounts, useFinanceCategories,
  useUpdateSettings, useCreateAccount, useCreateCategory, useImportCSV,
  formatMoney,
} from "@/hooks/use-finance"

import { cn } from "@/lib/utils"

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold">{title}</h3>
      {children}
    </div>
  )
}

export default function FinanceSettingsPage({ params }: { params: Promise<{ workspaceId: string }> }) {
  const { workspaceId } = use(params)

  const { data: settings } = useFinanceSettings(workspaceId)
  const { data: accounts = [] } = useFinanceAccounts(workspaceId)
  const { data: categories = [] } = useFinanceCategories(workspaceId)

  const updateSettings = useUpdateSettings(workspaceId)
  const createAccount = useCreateAccount(workspaceId)
  const createCategory = useCreateCategory(workspaceId)
  const importCSV = useImportCSV(workspaceId)

  const [currency, setCurrency] = useState("")
  const [importResult, setImportResult] = useState<{ imported: number; skipped: number; errors: string[] } | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  // New account form state
  const [accForm, setAccForm] = useState({ name: "", type: "bank", opening_balance: "0" })
  const [showAccForm, setShowAccForm] = useState(false)
  const [catForm, setCatForm] = useState({ name: "", kind: "expense" })
  const [showCatForm, setShowCatForm] = useState(false)

  return (
    <div className="p-6 space-y-8 max-w-2xl">
      {/* ── Currency ──────────────────────────────────────────────────────── */}
      <Section title="Workspace Currency">
        <div className="rounded-xl border border-border/60 bg-card p-4 space-y-3">
          <div className="flex items-center gap-3">
            <div>
              <label className="text-xs font-medium text-muted-foreground">Base Currency</label>
              <div className="flex gap-2 mt-1">
                <input
                  className="rounded-lg border border-border/60 bg-background text-foreground px-3 py-2 text-sm w-24"
                  maxLength={3}
                  placeholder={settings?.base_currency ?? "INR"}
                  value={currency}
                  onChange={e => setCurrency(e.target.value.toUpperCase())}
                />
                <button
                  disabled={!currency || updateSettings.isPending}
                  onClick={() => updateSettings.mutate({ base_currency: currency }, { onSuccess: () => setCurrency("") })}
                  className="rounded-lg bg-foreground text-background px-3 py-2 text-sm disabled:opacity-40"
                >
                  Save
                </button>
              </div>
            </div>
            <div className="text-sm text-muted-foreground">
              Current: <strong>{settings?.base_currency ?? "INR"}</strong>
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            ⚠️ Changing currency does not convert existing transactions. Use for new workspaces or same-currency migrations.
          </p>
        </div>
      </Section>

      {/* ── Accounts ──────────────────────────────────────────────────────── */}
      <Section title="Accounts">
        <div className="rounded-xl border border-border/60 bg-card overflow-hidden">
          {accounts.length > 0 && (
            <table className="w-full text-sm">
              <thead className="bg-muted/40 border-b border-border/60">
                <tr>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground">Name</th>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground">Type</th>
                  <th className="text-right px-4 py-2.5 text-xs font-medium text-muted-foreground">Balance</th>
                  <th className="text-center px-4 py-2.5 text-xs font-medium text-muted-foreground">Active</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {accounts.map(acc => (
                  <tr key={acc.id}>
                    <td className="px-4 py-2.5 font-medium">{acc.name}</td>
                    <td className="px-4 py-2.5 capitalize text-muted-foreground text-xs">{acc.type}</td>
                    <td className="px-4 py-2.5 text-right text-sm">{formatMoney(acc.balance_cents)}</td>
                    <td className="px-4 py-2.5 text-center">
                      {acc.is_active ? <CheckCircle2 size={14} className="text-emerald-500 mx-auto" /> : <span className="text-xs text-muted-foreground">Off</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {showAccForm ? (
            <form
              className="p-4 border-t border-border/60 space-y-3"
              onSubmit={e => {
                e.preventDefault()
                createAccount.mutate({
                  name: accForm.name,
                  type: accForm.type,
                  opening_balance_cents: Math.round(parseFloat(accForm.opening_balance || "0") * 100),
                }, { onSuccess: () => { setShowAccForm(false); setAccForm({ name: "", type: "bank", opening_balance: "0" }) } })
              }}
            >
              <div className="grid grid-cols-3 gap-3">
                <div className="col-span-1">
                  <label className="text-xs font-medium text-muted-foreground">Name</label>
                  <input required className="mt-1 w-full rounded-lg border border-border/60 bg-background text-foreground px-3 py-2 text-sm"
                    placeholder="HDFC Current"
                    value={accForm.name} onChange={e => setAccForm(f => ({ ...f, name: e.target.value }))} />
                </div>
                <div>
                  <label className="text-xs font-medium text-muted-foreground">Type</label>
                  <select className="mt-1 w-full rounded-lg border border-border/60 bg-background text-foreground px-3 py-2 text-sm"
                    value={accForm.type} onChange={e => setAccForm(f => ({ ...f, type: e.target.value }))}>
                    <option value="bank">Bank</option>
                    <option value="cash">Cash</option>
                    <option value="other">Other</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-muted-foreground">Opening Balance</label>
                  <input type="number" step="0.01" className="mt-1 w-full rounded-lg border border-border/60 bg-background text-foreground px-3 py-2 text-sm"
                    value={accForm.opening_balance} onChange={e => setAccForm(f => ({ ...f, opening_balance: e.target.value }))} />
                </div>
              </div>
              <div className="flex gap-2 justify-end">
                <button type="button" onClick={() => setShowAccForm(false)} className="rounded-lg border border-border/60 px-3 py-1.5 text-sm hover:bg-muted">Cancel</button>
                <button type="submit" disabled={createAccount.isPending} className="rounded-lg bg-foreground text-background px-3 py-1.5 text-sm disabled:opacity-40">
                  {createAccount.isPending ? "Saving…" : "Add Account"}
                </button>
              </div>
            </form>
          ) : (
            <div className="p-3 border-t border-border/40">
              <button onClick={() => setShowAccForm(true)} className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
                <Plus size={14} /> Add account
              </button>
            </div>
          )}
        </div>
      </Section>

      {/* ── Categories ────────────────────────────────────────────────────── */}
      <Section title="Categories">
        <div className="rounded-xl border border-border/60 bg-card overflow-hidden">
          <div className="grid grid-cols-2 divide-x divide-border/40">
            <div>
              <p className="px-4 py-2 text-xs font-medium text-emerald-500 bg-emerald-500/8 border-b border-border/40">Income</p>
              {categories.filter(c => c.kind === "income").map(c => (
                <div key={c.id} className="flex items-center justify-between px-4 py-2 border-b border-border/30 last:border-0">
                  <span className="text-sm">{c.name}</span>
                  {c.is_system && <span className="text-xs text-muted-foreground">system</span>}
                </div>
              ))}
            </div>
            <div>
              <p className="px-4 py-2 text-xs font-medium text-rose-500 bg-rose-500/8 border-b border-border/40">Expense</p>
              {categories.filter(c => c.kind === "expense").map(c => (
                <div key={c.id} className="flex items-center justify-between px-4 py-2 border-b border-border/30 last:border-0">
                  <span className="text-sm">{c.name}</span>
                  {c.is_system && <span className="text-xs text-muted-foreground">system</span>}
                </div>
              ))}
            </div>
          </div>

          {showCatForm ? (
            <form className="p-4 border-t border-border/60 flex gap-3 items-end"
              onSubmit={e => {
                e.preventDefault()
                createCategory.mutate({ name: catForm.name, kind: catForm.kind }, { onSuccess: () => { setShowCatForm(false); setCatForm({ name: "", kind: "expense" }) } })
              }}
            >
              <div className="flex-1">
                <label className="text-xs font-medium text-muted-foreground">Name</label>
                <input required className="mt-1 w-full rounded-lg border border-border/60 bg-background text-foreground px-3 py-2 text-sm"
                  value={catForm.name} onChange={e => setCatForm(f => ({ ...f, name: e.target.value }))} />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">Kind</label>
                <select className="mt-1 w-full rounded-lg border border-border/60 bg-background text-foreground px-3 py-2 text-sm"
                  value={catForm.kind} onChange={e => setCatForm(f => ({ ...f, kind: e.target.value }))}>
                  <option value="income">Income</option>
                  <option value="expense">Expense</option>
                </select>
              </div>
              <button type="button" onClick={() => setShowCatForm(false)} className="rounded-lg border border-border/60 px-3 py-2 text-sm hover:bg-muted">Cancel</button>
              <button type="submit" disabled={createCategory.isPending} className="rounded-lg bg-foreground text-background px-3 py-2 text-sm disabled:opacity-40">Add</button>
            </form>
          ) : (
            <div className="p-3 border-t border-border/40">
              <button onClick={() => setShowCatForm(true)} className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
                <Plus size={14} /> Add category
              </button>
            </div>
          )}
        </div>
      </Section>

      {/* ── CSV Import ────────────────────────────────────────────────────── */}
      <Section title="Import Transactions (CSV)">
        <div className="rounded-xl border border-border/60 bg-card p-4 space-y-3">
          <p className="text-xs text-muted-foreground">
            Expected columns: <code className="bg-muted px-1 rounded">date, description, amount, type (income/expense), category, account</code>
            <br />Unknown categories fall back to "Other". Unknown accounts are skipped with an error.
          </p>
          <input
            ref={fileRef}
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={e => {
              const file = e.target.files?.[0]
              if (!file) return
              setImportResult(null)
              importCSV.mutate(file, {
                onSuccess: (data) => { setImportResult(data); if (fileRef.current) fileRef.current.value = "" },
              })
            }}
          />
          <button
            onClick={() => fileRef.current?.click()}
            disabled={importCSV.isPending}
            className="flex items-center gap-2 rounded-xl border border-border/60 px-4 py-2.5 text-sm font-medium hover:bg-muted disabled:opacity-40 transition-colors"
          >
            <Upload size={15} />
            {importCSV.isPending ? "Importing…" : "Choose CSV file"}
          </button>

          {importResult && (
            <div className={cn(
              "rounded-lg p-3 text-sm",
              importResult.errors.length > 0 ? "bg-amber-500/10 border border-amber-500/30" : "bg-emerald-500/10 border border-emerald-500/30"
            )}>
              <p className="font-medium">
                ✓ {importResult.imported} imported · {importResult.skipped} skipped
              </p>
              {importResult.errors.length > 0 && (
                <ul className="mt-2 space-y-0.5 text-xs text-amber-600 dark:text-amber-400">
                  {importResult.errors.map((err, i) => <li key={i}>• {err}</li>)}
                </ul>
              )}
            </div>
          )}
        </div>
      </Section>
    </div>
  )
}

