/**
 * useTheme — Light / Dark / System theme picker state.
 *
 * Storage: localStorage('em-copilot-theme')
 * Effect:  toggles the `dark` class on <html> so Tailwind v4 dark variant fires.
 *
 * FOUC handling: an inline <script> in index.html applies the dark class BEFORE
 * React mounts. This hook keeps the React state in sync after that.
 */
import { useCallback, useEffect, useState } from "react";

export type Theme = "light" | "dark" | "system";

const STORAGE_KEY = "em-copilot-theme";

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
  // Light is the public-demo default. Users can opt into Dark or System via the
  // picker; their choice is persisted. (Defaulting to System would mean Mac users
  // in dark mode land on dark, which contradicts the design goal of "light first".)
  return "light";
}

export function useTheme() {
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

  // Re-apply on mount in case the inline script + React state drift.
  useEffect(() => {
    applyThemeClass(theme);
  }, [theme]);

  // When in "system" mode, respond to OS-level theme changes live.
  useEffect(() => {
    if (theme !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => applyThemeClass("system");
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [theme]);

  return { theme, setTheme };
}
