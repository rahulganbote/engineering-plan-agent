import { useEffect, useState } from 'react';
import { AuthProvider } from './context/AuthContext';
import { WorkspaceProvider } from './context/WorkspaceContext';
import { AgentWorkspace } from './components/AgentWorkspace';
import { AboutPage } from './components/AboutPage';
import { Toaster } from 'sonner';
import { ThemeProvider, useTheme } from './hooks/useTheme';

/**
 * ThemedToaster - Sonner toaster that follows the active theme picked in the
 * header. Without this wrapper, Toaster is locked to whatever theme prop you
 * hardcode, which desyncs from the rest of the UI when the user changes
 * Light / Dark / System.
 */
function ThemedToaster() {
  const { theme } = useTheme();
  return <Toaster position="top-right" theme={theme} closeButton />;
}

/**
 * Hash-based routing — one extra "page" (the About page) doesn't justify
 * pulling in react-router-dom. Hash routing avoids any FastAPI changes and
 * survives page refresh without 404s.
 */
function useHashRoute(): string {
  const [hash, setHash] = useState<string>(window.location.hash);
  useEffect(() => {
    const onHashChange = () => setHash(window.location.hash);
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);
  return hash;
}

function App() {
  const hash = useHashRoute();
  const isAbout = hash === '#/about';

  return (
    <ThemeProvider>
      <AuthProvider>
        <WorkspaceProvider>
          {isAbout ? <AboutPage /> : <AgentWorkspace />}
          <ThemedToaster />
        </WorkspaceProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
