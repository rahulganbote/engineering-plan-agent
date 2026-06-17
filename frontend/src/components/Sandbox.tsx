import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';
import { PlanSkeleton } from './PlanSkeleton';
import { Sparkles, Terminal, AlertCircle, Info, RefreshCw } from 'lucide-react';

export const Sandbox: React.FC = () => {
  const [clickCount, setClickCount] = useState(0);
  const [activeTab, setActiveTab] = useState<'buttons' | 'badges' | 'alerts' | 'cards' | 'skeletons'>('buttons');

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-8 font-sans">
      <header className="max-w-6xl mx-auto mb-8 border-b border-slate-800 pb-6 flex items-center justify-between">
        <div>
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 text-xs font-semibold uppercase tracking-wider mb-2">
            <Sparkles size={12} /> Component Sandbox
          </span>
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-100">Storybook-style Sandbox</h1>
          <p className="text-slate-400 text-sm mt-1">
            Previewing UI elements in isolation under the Dark Slate design system.
          </p>
        </div>
      </header>

      <main className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-4 gap-8">
        {/* Navigation Sidebar */}
        <aside className="space-y-1">
          <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider px-3 mb-2">Components</h3>
          {(['buttons', 'badges', 'alerts', 'cards', 'skeletons'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm font-semibold transition ${
                activeTab === tab 
                  ? 'bg-indigo-600 text-white shadow-md' 
                  : 'text-slate-400 hover:bg-slate-900 hover:text-slate-200'
              }`}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </aside>

        {/* Component Showcase Area */}
        <section className="md:col-span-3 bg-slate-900 border border-slate-800 rounded-xl p-8 shadow-xl min-h-[400px]">
          {activeTab === 'buttons' && (
            <div className="space-y-6">
              <h2 className="text-lg font-bold border-b border-slate-800 pb-2 text-slate-200">Buttons</h2>
              <div className="flex flex-wrap gap-4 items-center">
                <Button variant="default" onClick={() => setClickCount(c => c + 1)}>
                  Default Button ({clickCount})
                </Button>
                <Button variant="secondary">Secondary Button</Button>
                <Button variant="outline">Outline Button</Button>
                <Button variant="ghost">Ghost Button</Button>
                <Button variant="link">Link Button</Button>
                <Button variant="destructive">Destructive Button</Button>
              </div>
              <div className="p-4 bg-slate-950 rounded border border-slate-850 text-xs text-slate-400 font-mono space-y-1">
                <div>Button imports: <code className="text-indigo-400">@/components/ui/button</code></div>
                <div>Variants demonstrated: <code className="text-slate-300">default, secondary, outline, ghost, link, destructive</code></div>
              </div>
            </div>
          )}

          {activeTab === 'badges' && (
            <div className="space-y-6">
              <h2 className="text-lg font-bold border-b border-slate-800 pb-2 text-slate-200">Badges</h2>
              <div className="flex flex-wrap gap-4">
                <Badge variant="default">Default Badge</Badge>
                <Badge variant="secondary">Secondary Badge</Badge>
                <Badge variant="outline">Outline Badge</Badge>
                <Badge variant="destructive">Destructive Badge</Badge>
                <Badge className="bg-green-950/50 text-green-400 border border-green-800/50">🟢 GREEN</Badge>
                <Badge className="bg-amber-950/50 text-amber-400 border border-amber-800/50">🟡 AMBER</Badge>
                <Badge className="bg-red-950/50 text-red-400 border border-red-800/50">🔴 RED</Badge>
              </div>
              <div className="p-4 bg-slate-950 rounded border border-slate-850 text-xs text-slate-400 font-mono">
                Badge imports: <code className="text-indigo-400">@/components/ui/badge</code>
              </div>
            </div>
          )}

          {activeTab === 'alerts' && (
            <div className="space-y-6">
              <h2 className="text-lg font-bold border-b border-slate-800 pb-2 text-slate-200">Alerts</h2>
              <div className="space-y-4">
                <Alert className="bg-slate-950 border border-slate-800">
                  <Terminal className="h-4 w-4 text-indigo-400" />
                  <AlertTitle className="text-slate-200">Heads up!</AlertTitle>
                  <AlertDescription className="text-slate-400">
                    You can add components to your app using the shadcn CLI.
                  </AlertDescription>
                </Alert>

                <Alert variant="destructive" className="bg-red-950/10 border-red-900/30 text-red-400">
                  <AlertCircle className="h-4 w-4 text-red-400" />
                  <AlertTitle>Error</AlertTitle>
                  <AlertDescription>
                    Your session has expired. Please log in again.
                  </AlertDescription>
                </Alert>

                <Alert className="bg-indigo-950/20 border-indigo-900/30 text-indigo-300">
                  <Info className="h-4 w-4 text-indigo-400" />
                  <AlertTitle>Information Banner</AlertTitle>
                  <AlertDescription>
                    This is an informational notice using dark indigo tones.
                  </AlertDescription>
                </Alert>
              </div>
            </div>
          )}

          {activeTab === 'cards' && (
            <div className="space-y-6">
              <h2 className="text-lg font-bold border-b border-slate-800 pb-2 text-slate-200">Cards</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Card className="bg-slate-950 border border-slate-850 shadow-sm">
                  <CardHeader>
                    <CardTitle className="text-slate-200 text-sm uppercase tracking-wide">Orchestrator Agent</CardTitle>
                    <CardDescription className="text-slate-500">Responsible for parsing BRD files.</CardDescription>
                  </CardHeader>
                  <CardContent className="text-slate-350 text-xs">
                    This is the standard workspace card format.
                  </CardContent>
                  <CardFooter className="flex justify-end gap-2 border-t border-slate-900 pt-3">
                    <Button variant="ghost" size="sm">Details</Button>
                    <Button variant="outline" size="sm">Configure</Button>
                  </CardFooter>
                </Card>

                <Card className="bg-slate-950 border border-slate-850 shadow-sm">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-slate-200 text-sm uppercase tracking-wide flex items-center justify-between">
                      <span>Live Status Monitor</span>
                      <RefreshCw size={14} className="text-indigo-400 animate-spin" />
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex justify-between items-center text-xs">
                      <span className="text-slate-500">Active Pipeline:</span>
                      <span className="font-semibold text-green-400">Online</span>
                    </div>
                    <div className="flex justify-between items-center text-xs">
                      <span className="text-slate-500">Run ID:</span>
                      <span className="font-mono text-slate-300">run-4091a</span>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>
          )}

          {activeTab === 'skeletons' && (
            <div className="space-y-6">
              <h2 className="text-lg font-bold border-b border-slate-800 pb-2 text-slate-200">Skeletons</h2>
              <PlanSkeleton />
            </div>
          )}
        </section>
      </main>
    </div>
  );
};
