/** Brand marks — Google Brand Resource Center, GitHub Logos and Usage, Workspace product icons */

import type { ComponentType, ReactNode } from "react"

// ── Parent brands ─────────────────────────────────────────────────────────────

export function GoogleLogo({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" role="img" aria-label="Google" xmlns="http://www.w3.org/2000/svg">
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
    </svg>
  )
}

export function GitHubLogo({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" role="img" aria-label="GitHub" xmlns="http://www.w3.org/2000/svg" fill="currentColor">
      <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
    </svg>
  )
}

// ── Google Workspace product icons (24×24, consistent viewBox) ────────────────

function ProductSvg({
  className,
  label,
  children,
}: {
  className?: string
  label: string
  children: ReactNode
}) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      role="img"
      aria-label={label}
      xmlns="http://www.w3.org/2000/svg"
    >
      {children}
    </svg>
  )
}

/** Fixed-size frame so icons don’t clip or bleed at small sizes */
export function GoogleProductLogo({
  Logo,
  size = 20,
  className,
}: {
  Logo: LogoComponent
  size?: number
  className?: string
}) {
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center overflow-hidden ${className ?? ""}`}
      style={{ width: size, height: size }}
    >
      <Logo className="h-full w-full" />
    </span>
  )
}

export function GmailLogo({ className }: { className?: string }) {
  return (
    <ProductSvg className={className} label="Gmail">
      <path
        fill="#EA4335"
        d="M24 5.457v13.909c0 .904-.732 1.636-1.636 1.636h-3.819V11.73L12 16.64l-6.545-4.91v9.273H1.636A1.636 1.636 0 0 1 0 19.366V5.457c0-2.023 2.309-3.178 3.927-1.964L12 10.09l8.073-6.597C21.69 2.28 24 3.434 24 5.457z"
      />
    </ProductSvg>
  )
}

export function GoogleDriveLogo({ className }: { className?: string }) {
  return (
    <ProductSvg className={className} label="Google Drive">
      <path fill="#0066DA" d="M4.8 4.2 1.2 10.5 7.8 21.7h12.6L23.4 10.5 19.8 4.2H4.8z" />
      <path fill="#00AC47" d="M12 4.2 22.2 21.7H12L1.8 4.2H12z" />
      <path fill="#FFBA00" d="M4.8 4.2 12 13.5 19.2 4.2H12L4.8 4.2z" />
    </ProductSvg>
  )
}

export function GoogleCalendarLogo({ className }: { className?: string }) {
  return (
    <ProductSvg className={className} label="Google Calendar">
      <path
        fill="#4285F4"
        d="M18 2h2a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h2V0h3v2h6V0h3v2zm1 8H5v8h14V10zM8 5H5v3h3V5zm11 0h-3v3h3V5z"
      />
      <path fill="#fff" d="M7 12h3v3H7v-3zm4 0h3v3h-3v-3zm4 0h3v3h-3v-3z" />
    </ProductSvg>
  )
}

export function GoogleSheetsLogo({ className }: { className?: string }) {
  return (
    <ProductSvg className={className} label="Google Sheets">
      <path
        fill="#0F9D58"
        d="M14.727 2H6.545A2.545 2.545 0 0 0 4 4.545v14.91a2.545 2.545 0 0 0 2.545 2.545h10.91A2.545 2.545 0 0 0 20 19.455V7.273L14.727 2z"
      />
      <path fill="#87CEAC" d="M14.727 2v5.273H20L14.727 2z" />
      <path
        fill="#fff"
        d="M7.5 11h9v1.5h-9V11zm0 3h9v1.5h-9V14zm0 3h6v1.5h-6V17z"
      />
    </ProductSvg>
  )
}

export function GoogleMeetLogo({ className }: { className?: string }) {
  return (
    <ProductSvg className={className} label="Google Meet">
      <path fill="#00897B" d="M2 6.5A2.5 2.5 0 0 1 4.5 4h11v16H4.5A2.5 2.5 0 0 1 2 17.5v-11z" />
      <path fill="#00BFA5" d="M17 8.5l7 3.5-7 3.5V8.5z" />
      <path fill="#fff" d="M6 10h5v4H6v-4z" />
    </ProductSvg>
  )
}

export type GoogleProductId = "gmail" | "drive" | "calendar" | "sheets" | "meet"

type LogoComponent = ComponentType<{ className?: string }>

export const GOOGLE_WORKSPACE_PRODUCTS: {
  id: GoogleProductId
  label: string
  Logo: LogoComponent
}[] = [
  { id: "gmail", label: "Gmail", Logo: GmailLogo },
  { id: "drive", label: "Drive", Logo: GoogleDriveLogo },
  { id: "calendar", label: "Calendar", Logo: GoogleCalendarLogo },
  { id: "sheets", label: "Sheets", Logo: GoogleSheetsLogo },
  { id: "meet", label: "Meet", Logo: GoogleMeetLogo },
]

/** Hermes MCP tools enabled for Google (matches hermes/config.yaml). */
export const GOOGLE_HERMES_TOOLS: { product: GoogleProductId; tools: string[] }[] = [
  {
    product: "gmail",
    tools: [
      "gmail_list_inbox",
      "gmail_search",
      "gmail_get_email",
      "gmail_send",
      "gmail_create_draft",
      "gmail_add_label",
      "gmail_archive",
    ],
  },
  {
    product: "drive",
    tools: [
      "gdrive_search",
      "gdrive_list_folder",
      "gdrive_read_file",
      "gdrive_get_file_info",
      "gdrive_upload_file",
    ],
  },
  {
    product: "calendar",
    tools: [
      "gcal_list_events",
      "gcal_find_free_slots",
      "gcal_create_event",
      "gcal_list_calendars",
      "gcal_create_event_with_meet",
      "gcal_update_event",
      "gcal_delete_event",
    ],
  },
  {
    product: "sheets",
    tools: [
      "gsheets_list_spreadsheets",
      "gsheets_get_metadata",
      "gsheets_read_range",
      "gsheets_append_row",
      "gsheets_update_cells",
    ],
  },
  {
    product: "meet",
    tools: ["gmeet_list_upcoming"],
  },
]

export function IntegrationBrandIcon({ provider }: { provider: "google" | "github" }) {
  if (provider === "google") {
    return (
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border bg-white p-2 shadow-sm">
        <GoogleLogo className="h-6 w-6" />
      </div>
    )
  }
  return (
    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border bg-white p-2 shadow-sm">
      <GitHubLogo className="h-6 w-6 text-[#24292f]" />
    </div>
  )
}

export function GoogleProductIcons({ size = "md" }: { size?: "sm" | "md" }) {
  const px = size === "sm" ? 20 : 24

  return (
    <div className="flex flex-wrap gap-2">
      {GOOGLE_WORKSPACE_PRODUCTS.map(({ id, label, Logo }) => (
        <div
          key={id}
          className="flex items-center gap-1.5 rounded-lg border border-border/50 bg-white px-2 py-1 shadow-sm"
          title={label}
        >
          <GoogleProductLogo Logo={Logo} size={px} />
          <span className="text-[10px] font-medium text-foreground/80">{label}</span>
        </div>
      ))}
    </div>
  )
}

export function GoogleHermesToolsPanel() {
  const productMap = Object.fromEntries(
    GOOGLE_WORKSPACE_PRODUCTS.map(p => [p.id, p])
  ) as Record<GoogleProductId, (typeof GOOGLE_WORKSPACE_PRODUCTS)[number]>

  return (
    <div className="mt-2 rounded-2xl border border-border/60 bg-white p-5 shadow-sm space-y-4">
      <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
        Google tools available to Hermes when connected
      </p>
      {GOOGLE_HERMES_TOOLS.map(({ product, tools }) => {
        const { label, Logo } = productMap[product]
        return (
          <div key={product}>
            <div className="flex items-center gap-2 mb-2">
              <GoogleProductLogo Logo={Logo} size={20} />
              <span className="text-xs font-semibold text-foreground">{label}</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {tools.map(t => (
                <span
                  key={t}
                  className="rounded-lg border border-border/50 bg-muted/30 px-2 py-0.5 font-mono text-[10px] text-foreground/80"
                >
                  {t}
                </span>
              ))}
            </div>
          </div>
        )
      })}
      <p className="text-[10px] text-muted-foreground pt-1 border-t border-border/40">
        Writes (send, upload, create event, sheet edits) require approval via Proposed Actions or Telegram.
      </p>
    </div>
  )
}
