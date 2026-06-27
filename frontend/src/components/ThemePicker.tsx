/**
 * ThemePicker — Light / Dark / System dropdown for the workspace header.
 *
 * Pattern matches industry standard (Linear, Vercel, Stripe, GitHub, Notion):
 * three options, current selection shown as an icon-only trigger to save
 * horizontal space in the header.
 */
import { useEffect, useRef, useState } from "react";
import { Sun, Moon, Monitor, ChevronDown, Check } from "lucide-react";
import { type Theme, useTheme } from "../hooks/useTheme";

interface ThemeOption {
  value: Theme;
  label: string;
  Icon: typeof Sun;
}

const OPTIONS: ThemeOption[] = [
  { value: "light", label: "Light", Icon: Sun },
  { value: "dark", label: "Dark", Icon: Moon },
  { value: "system", label: "System", Icon: Monitor },
];

export function ThemePicker() {
  const { theme, setTheme } = useTheme();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Click-outside to close
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const current = OPTIONS.find((o) => o.value === theme) ?? OPTIONS[2];
  const TriggerIcon = current.Icon;

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label={`Theme: ${current.label}`}
        title={`Theme: ${current.label}`}
        className="flex items-center gap-1 px-2 py-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
      >
        <TriggerIcon size={14} />
        <ChevronDown
          size={10}
          className={`transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 top-full mt-1 w-36 bg-popover text-popover-foreground border border-border rounded-md shadow-lg overflow-hidden z-50"
        >
          {OPTIONS.map((opt) => {
            const OptIcon = opt.Icon;
            const selected = opt.value === theme;
            return (
              <button
                key={opt.value}
                role="menuitemradio"
                aria-checked={selected}
                onClick={() => {
                  setTheme(opt.value);
                  setOpen(false);
                }}
                className={`w-full flex items-center justify-between gap-2 px-3 py-2 text-xs transition-colors ${
                  selected
                    ? "bg-secondary text-foreground font-medium"
                    : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                }`}
              >
                <span className="flex items-center gap-2">
                  <OptIcon size={12} />
                  {opt.label}
                </span>
                {selected && <Check size={12} className="text-primary" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
