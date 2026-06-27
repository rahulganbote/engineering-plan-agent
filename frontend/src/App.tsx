import { AuthProvider } from './context/AuthContext';
import { WorkspaceProvider } from './context/WorkspaceContext';
import { AgentWorkspace } from './components/AgentWorkspace';
import { Toaster } from 'sonner';
import { ThemeProvider, useTheme } from './hooks/useTheme';

/**
 * ThemedToaster — Sonner toaster that follows the active theme picked in the
 * header. Without this wrapper, Toaster is locked to whatever theme prop you
 * hardcode, which desyncs from the rest of the UI when the user changes
 * Light / Dark / System.
 */
function ThemedToaster() {
  const { theme } = useTheme();
  return <Toaster position="top-right" theme={theme} closeButton />;
}

function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <WorkspaceProvider>
          <AgentWorkspace />
          <ThemedToaster />
        </WorkspaceProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
