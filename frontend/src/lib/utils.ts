import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

/**
 * Merge Tailwind classes safely.
 * Lets you write `cn("p-2", isActive && "p-4")` and have the conflicting
 * padding handled correctly (last one wins).
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
