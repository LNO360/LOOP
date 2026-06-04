export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="w-full max-w-md px-6">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold tracking-tight">Loop</h1>
          <p className="text-sm text-muted-foreground mt-1">Your company&apos;s operating system</p>
        </div>
        {children}
      </div>
    </div>
  )
}
