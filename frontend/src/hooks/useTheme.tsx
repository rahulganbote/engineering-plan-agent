/* eslint-disable react-refresh/only-export-components */
/**
 * Theme system — Light / Dark / System picker state, shared app-wide.
 *
 * Why a Context (not just a hook):
 *   Every `useState` inside a hook is INSTANCE-LOCAL. If two components
 *   (e.g. ThemePicker + ThemedToaster) each called a hook-only useTheme(),
 *   they'd hold separate state copies and desync the moment the user picks
 *   a different theme. The provider gives both consumers ONE state object.
 *
 * Storage: localStorage('em-copilot-theme')
 * Effect:  toggles the `dark` class on <html> so Tailwind v4 dark variant fires.
 *
 * FOUC handling: an inline <script> in index.html applies the dark class BEFORE
 * React mounts. This hook keeps the React state in sync after that.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

export type Theme = "light" | "dark" | "system";

const STORAGE_KEY = "em-copilot-theme";

interface ThemeContextValue {
  theme: Theme;
  setTheme: (next: Theme) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

function resolveIsDark(mode: Theme): boolean {
  if (mode === "dark") return true;
  if (mode === "light") return false;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function applyThemeClass(mode: Theme): void {
  const isDark = resolveIsDark(mode);
  document.documentElement.classList.toggle("dark", isDark);
}

function readStoredTheme(): Theme {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark" || stored === "system") {
      return stored;
    }
  } catch {
    // localStorage blocked (private mode / sandbox) — fall back to light
  }
  // Light is the public-demo default. Users can opt into Dark or System via
  // the picker; their choice is persisted. (Defaulting to System would mean
  // Mac users in dark mode land on dark, which contradicts "light first".)
  return "light";
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(readStoredTheme);

  const setTheme = useCallback((next: Theme) => {
    setThemeState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // ignore — theme still applies for this session
    }
    applyThemeClass(next);
  }, []);

  // Re-apply on mount + whenever theme changes (covers inline-script vs
  // React-state drift, plus picker changes).
  useEffect(() => {
    applyThemeClass(theme);
  }, [theme]);

  // When in "system" mode, respond live to OS-level theme changes.
  useEffect(() => {
    if (theme !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => applyThemeClass("system");
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [theme]);

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme must be used within a <ThemeProvider>");
  }
  return ctx;
}
