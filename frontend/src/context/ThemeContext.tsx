import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';

type Theme = 'light' | 'dark' | 'auto';
type GlassStyle = 'clear' | 'tinted';

interface ThemeContextType {
  theme: Theme;
  glassStyle: GlassStyle;
  setTheme: (theme: Theme) => void;
  setGlassStyle: (style: GlassStyle) => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export const ThemeProvider = ({ children }: { children: ReactNode }) => {
  const [theme, setTheme] = useState<Theme>(() => {
    if (typeof window !== 'undefined' && window.localStorage) {
      return (window.localStorage.getItem('theme') as Theme) || 'dark';
    }
    return 'dark';
  });
  const [glassStyle, setGlassStyle] = useState<GlassStyle>(() => {
    if (typeof window !== 'undefined' && window.localStorage) {
      return (window.localStorage.getItem('glass-style') as GlassStyle) || 'clear';
    }
    return 'clear';
  });

  useEffect(() => {
    const root = window.document.documentElement;
    let resolvedTheme = theme;

    if (theme === 'auto') {
      resolvedTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }

    if (resolvedTheme === 'dark') {
      root.classList.add('dark');
      root.style.colorScheme = 'dark';
    } else {
      root.classList.remove('dark');
      root.style.colorScheme = 'light';
    }

    if (typeof window !== 'undefined' && window.localStorage) {
      window.localStorage.setItem('theme', theme);
    }
  }, [theme]);

  useEffect(() => {
    const root = window.document.documentElement;
    if (glassStyle === 'clear') {
      root.classList.add('glass-clear');
      root.classList.remove('glass-tinted');
    } else {
      root.classList.add('glass-tinted');
      root.classList.remove('glass-clear');
    }
    if (typeof window !== 'undefined' && window.localStorage) {
      window.localStorage.setItem('glass-style', glassStyle);
    }
  }, [glassStyle]);

  return (
    <ThemeContext.Provider value={{ theme, glassStyle, setTheme, setGlassStyle }}>
      {children}
    </ThemeContext.Provider>
  );
};

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) throw new Error('useTheme must be used within a ThemeProvider');
  return context;
};
