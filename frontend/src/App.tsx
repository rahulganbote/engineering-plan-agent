import { Button } from "@/components/ui/button"

// Sprint 0 placeholder. Sprint 1 replaces this with <AgentWorkspace />.
function App() {
  return (
    <main className="min-h-screen flex items-center justify-center bg-slate-950 text-slate-100 p-8">
      <div className="max-w-md text-center space-y-6">
        <h1 className="text-3xl font-bold tracking-tight">EM Copilot — React UI</h1>
        <p className="text-slate-400 text-sm">
          Sprint 0 scaffold. The real workspace lands in Sprint 1.
        </p>
        <div className="flex justify-center gap-3">
          <Button variant="default">Primary</Button>
          <Button variant="outline">Secondary</Button>
          <Button variant="ghost">Ghost</Button>
        </div>
        <span className="inline-block px-3 py-1 rounded-full bg-indigo-600/20 border border-indigo-600/40 text-indigo-300 text-xs font-semibold">
          Vite + React 19 + TS + Tailwind v4 + shadcn
        </span>
      </div>
    </main>
  )
}
export default App
