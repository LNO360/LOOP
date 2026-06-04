import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"

const base = (wsId: string) => `/workspaces/${wsId}/finance`

// ── Types ─────────────────────────────────────────────────────────────────────
export interface FinanceOverview {
  cash_position_cents: number
  mtd_revenue_cents: number
  mtd_expense_cents: number
  mtd_net_cents: number
  unpaid_invoices_count: number
  unpaid_invoices_total_cents: number
}

export interface FinanceSummary {
  period: string
  from_date: string
  to_date: string
  revenue_cents: number
  expense_cents: number
  net_cents: number
}

export interface FinanceAccount {
  id: string
  name: string
  type: "cash" | "bank" | "other"
  balance_cents: number
  opening_balance_cents: number
  opening_balance_date?: string
  is_active: boolean
  notes?: string
}

export interface FinanceCategory {
  id: string
  name: string
  kind: "income" | "expense"
  is_system: boolean
  sort_order: number
}

export interface FinanceTransaction {
  id: string
  account_id: string
  category_id?: string
  direction: "income" | "expense"
  amount_cents: number
  currency: string
  occurred_on: string
  description: string
  reference?: string
  source: string
  created_at: string
}

export interface FinanceInvoice {
  id: string
  customer_name: string
  amount_cents: number
  currency: string
  issued_on?: string
  due_on?: string
  status: "draft" | "sent" | "paid" | "void"
  paid_on?: string
  notes?: string
  linked_transaction_id?: string
  overdue: boolean
  created_at: string
}

export interface FinanceSettings {
  workspace_id: string
  base_currency: string
  fiscal_year_start_month: number
}

// ── Formatters ────────────────────────────────────────────────────────────────
export function formatMoney(cents: number, currency = "INR"): string {
  const amount = cents / 100
  if (currency === "INR") {
    return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(amount)
  }
  return new Intl.NumberFormat("en-US", { style: "currency", currency, maximumFractionDigits: 0 }).format(amount)
}

// ── Hooks ─────────────────────────────────────────────────────────────────────

export function useFinanceOverview(workspaceId: string) {
  return useQuery<FinanceOverview>({
    queryKey: ["finance", workspaceId, "overview"],
    queryFn: () => api.get(`${base(workspaceId)}/overview`).then(r => r.data),
  })
}

export function useFinanceSummary(workspaceId: string, period?: string) {
  return useQuery<FinanceSummary>({
    queryKey: ["finance", workspaceId, "summary", period],
    queryFn: () => api.get(`${base(workspaceId)}/summary`, { params: period ? { period } : {} }).then(r => r.data),
  })
}

export function useFinanceAccounts(workspaceId: string) {
  return useQuery<FinanceAccount[]>({
    queryKey: ["finance", workspaceId, "accounts"],
    queryFn: () => api.get(`${base(workspaceId)}/accounts`).then(r => r.data),
  })
}

export function useFinanceCategories(workspaceId: string) {
  return useQuery<FinanceCategory[]>({
    queryKey: ["finance", workspaceId, "categories"],
    queryFn: () => api.get(`${base(workspaceId)}/categories`).then(r => r.data),
  })
}

export function useFinanceTransactions(workspaceId: string, params?: {
  from_date?: string
  to_date?: string
  direction?: string
  category_id?: string
  account_id?: string
  limit?: number
}) {
  return useQuery<FinanceTransaction[]>({
    queryKey: ["finance", workspaceId, "transactions", params],
    queryFn: () => api.get(`${base(workspaceId)}/transactions`, { params: params || {} }).then(r => r.data),
  })
}

export function useFinanceInvoices(workspaceId: string, status?: string) {
  return useQuery<FinanceInvoice[]>({
    queryKey: ["finance", workspaceId, "invoices", status],
    queryFn: () => api.get(`${base(workspaceId)}/invoices`, { params: status ? { status } : {} }).then(r => r.data),
  })
}

export function useFinanceSettings(workspaceId: string) {
  return useQuery<FinanceSettings>({
    queryKey: ["finance", workspaceId, "settings"],
    queryFn: () => api.get(`${base(workspaceId)}/settings`).then(r => r.data),
  })
}

// ── Mutations ─────────────────────────────────────────────────────────────────

export function useCreateTransaction(workspaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Partial<FinanceTransaction> & { account_id: string; direction: string; amount_cents: number; occurred_on: string; description: string }) =>
      api.post(`${base(workspaceId)}/transactions`, data).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance", workspaceId] }),
  })
}

export function useUpdateTransaction(workspaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...data }: { id: string } & Partial<FinanceTransaction>) =>
      api.patch(`${base(workspaceId)}/transactions/${id}`, data).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance", workspaceId] }),
  })
}

export function useDeleteTransaction(workspaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.delete(`${base(workspaceId)}/transactions/${id}`).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance", workspaceId] }),
  })
}

export function useCreateInvoice(workspaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { customer_name: string; amount_cents: number; currency?: string; due_on?: string; notes?: string }) =>
      api.post(`${base(workspaceId)}/invoices`, data).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance", workspaceId] }),
  })
}

export function useUpdateInvoice(workspaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...data }: { id: string } & Partial<FinanceInvoice> & { account_id?: string }) =>
      api.patch(`${base(workspaceId)}/invoices/${id}`, data).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance", workspaceId] }),
  })
}

export function useCreateAccount(workspaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { name: string; type: string; opening_balance_cents?: number; notes?: string }) =>
      api.post(`${base(workspaceId)}/accounts`, data).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance", workspaceId] }),
  })
}

export function useUpdateSettings(workspaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { base_currency?: string; fiscal_year_start_month?: number }) =>
      api.patch(`${base(workspaceId)}/settings`, data).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance", workspaceId] }),
  })
}

export function useCreateCategory(workspaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { name: string; kind: string }) =>
      api.post(`${base(workspaceId)}/categories`, data).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance", workspaceId] }),
  })
}

export function useImportCSV(workspaceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => {
      const form = new FormData()
      form.append("file", file)
      return api.post(`${base(workspaceId)}/transactions/import`, form, {
        headers: { "Content-Type": "multipart/form-data" },
      }).then(r => r.data)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance", workspaceId] }),
  })
}
