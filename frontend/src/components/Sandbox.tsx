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
    <div className="min-h-screen bg-background text-foreground p-8 font-sans">
      <header className="max-w-6xl mx-auto mb-8 border-b border-border pb-6 flex items-center justify-between">
        <div>
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-primary/10 border border-primary/30 text-primary text-xs font-semibold uppercase tracking-wider mb-2">
            <Sparkles size={12} /> Component Sandbox
          </span>
          <h1 className="text-3xl font-extrabold tracking-tight text-foreground">Storybook-style Sandbox</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Previewing UI elements in isolation under the Dark Slate design system.
          </p>
        </div>
      </header>

      <main className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-4 gap-8">
        {/* Navigation Sidebar */}
        <aside className="space-y-1">
          <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-wider px-3 mb-2">Components</h3>
          {(['buttons', 'badges', 'alerts', 'cards', 'skeletons'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm font-semibold transition ${
                activeTab === tab 
                  ? 'bg-primary text-white shadow-md' 
                  : 'text-muted-foreground hover:bg-card hover:text-foreground'
              }`}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </aside>

        {/* Component Showcase Area */}
        <section className="md:col-span-3 bg-card border border-border rounded-xl p-8 shadow-xl min-h-[400px]">
          {activeTab === 'buttons' && (
            <div className="space-y-6">
              <h2 className="text-lg font-bold border-b border-border pb-2 text-foreground">Buttons</h2>
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
              <div className="p-4 bg-background rounded border border-border text-xs text-muted-foreground font-mono space-y-1">
                <div>Button imports: <code className="text-primary">@/components/ui/button</code></div>
                <div>Variants demonstrated: <code className="text-foreground">default, secondary, outline, ghost, link, destructive</code></div>
              </div>
            </div>
          )}

          {activeTab === 'badges' && (
            <div className="space-y-6">
              <h2 className="text-lg font-bold border-b border-border pb-2 text-foreground">Badges</h2>
              <div className="flex flex-wrap gap-4">
                <Badge variant="default">Default Badge</Badge>
                <Badge variant="secondary">Secondary Badge</Badge>
                <Badge variant="outline">Outline Badge</Badge>
                <Badge variant="destructive">Destructive Badge</Badge>
                <Badge className="bg-success/20 text-success border border-success/40">🟢 GREEN</Badge>
                <Badge className="bg-warning/50 text-warning border border-warning/50">🟡 AMBER</Badge>
                <Badge className="bg-danger/50 text-danger border border-danger/50">🔴 RED</Badge>
              </div>
              <div className="p-4 bg-background rounded border border-border text-xs text-muted-foreground font-mono">
                Badge imports: <code className="text-primary">@/components/ui/badge</code>
              </div>
            </div>
          )}

          {activeTab === 'alerts' && (
            <div className="space-y-6">
              <h2 className="text-lg font-bold border-b border-border pb-2 text-foreground">Alerts</h2>
              <div className="space-y-4">
                <Alert className="bg-background border border-border">
                  <Terminal className="h-4 w-4 text-primary" />
                  <AlertTitle className="text-foreground">Heads up!</AlertTitle>
                  <AlertDescription className="text-muted-foreground">
                    You can add components to your app using the shadcn CLI.
                  </AlertDescription>
                </Alert>

                <Alert variant="destructive" className="bg-danger/10 border-danger/30 text-danger">
                  <AlertCircle className="h-4 w-4 text-danger" />
                  <AlertTitle>Error</AlertTitle>
                  <AlertDescription>
                    Your session has expired. Please log in again.
                  </AlertDescription>
                </Alert>

                <Alert className="bg-primary/10 border-primary/30 text-primary">
                  <Info className="h-4 w-4 text-primary" />
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
              <h2 className="text-lg font-bold border-b border-border pb-2 text-foreground">Cards</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Card className="bg-background border border-border shadow-sm">
                  <CardHeader>
                    <CardTitle className="text-foreground text-sm uppercase tracking-wide">Orchestrator Agent</CardTitle>
                    <CardDescription className="text-muted-foreground">Responsible for parsing BRD files.</CardDescription>
                  </CardHeader>
                  <CardContent className="text-muted-foreground text-xs">
                    This is the standard workspace card format.
                  </CardContent>
                  <CardFooter className="flex justify-end gap-2 border-t border-border pt-3">
                    <Button variant="ghost" size="sm">Details</Button>
                    <Button variant="outline" size="sm">Configure</Button>
                  </CardFooter>
                </Card>

                <Card className="bg-background border border-border shadow-sm">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-foreground text-sm uppercase tracking-wide flex items-center justify-between">
                      <span>Live Status Monitor</span>
                      <RefreshCw size={14} className="text-primary animate-spin" />
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex justify-between items-center text-xs">
                      <span className="text-muted-foreground">Active Pipeline:</span>
                      <span className="font-semibold text-success">Online</span>
                    </div>
                    <div className="flex justify-between items-center text-xs">
                      <span className="text-muted-foreground">Run ID:</span>
                      <span className="font-mono text-foreground">run-4091a</span>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>
          )}

          {activeTab === 'skeletons' && (
            <div className="space-y-6">
              <h2 className="text-lg font-bold border-b border-border pb-2 text-foreground">Skeletons</h2>
              <PlanSkeleton />
            </div>
          )}
        </section>
      </main>
    </div>
  );
};
