import { useState } from 'react';
import { ThemeProvider } from './context/ThemeContext';
import { AuthProvider } from './context/AuthContext';
import { WorkspaceProvider } from './context/WorkspaceContext';
import { AgentWorkspace } from './components/AgentWorkspace';
import { Sandbox } from './components/Sandbox';
import { Button } from '@/components/ui/button';
import { Sparkles, Terminal } from 'lucide-react';
import { Toaster } from 'sonner';

function App() {
  const [view, setView] = useState<'workspace' | 'sandbox'>('workspace');

  return (
    <ThemeProvider>
      <AuthProvider>
        <WorkspaceProvider>
          {/* Floating View Switcher */}
          <div className="fixed bottom-4 right-4 z-50 bg-slate-900/90 border border-slate-800 p-1.5 rounded-lg shadow-xl flex items-center gap-1.5 backdrop-blur">
            <Button 
              variant={view === 'workspace' ? 'default' : 'ghost'} 
              size="sm" 
              onClick={() => setView('workspace')}
              className="text-xs flex items-center gap-1"
            >
              <Terminal size={12} /> Workspace
            </Button>
            <Button 
              variant={view === 'sandbox' ? 'default' : 'ghost'} 
              size="sm" 
              onClick={() => setView('sandbox')}
              className="text-xs flex items-center gap-1"
            >
              <Sparkles size={12} /> Sandbox
            </Button>
          </div>

          {view === 'workspace' ? <AgentWorkspace /> : <Sandbox />}
          
          {/* Sonner toast container */}
          <Toaster position="top-right" theme="dark" closeButton />
        </WorkspaceProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
