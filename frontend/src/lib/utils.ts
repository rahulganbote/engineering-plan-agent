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

/**
 * Convert raw API/LLM error messages into clean, user-friendly feedback.
 */
export function cleanLlmErrorMessage(rawMessage: string): string {
  if (!rawMessage) return "An unexpected error occurred.";

  const lower = rawMessage.toLowerCase();

  // Insufficient quota / 429
  if (
    lower.includes("insufficient_quota") ||
    lower.includes("quota exceeded") ||
    lower.includes("exceeded your current quota")
  ) {
    return "API quota exceeded. Please check try again later or contact [EMAIL_ADDRESS] to extend the quota.";
  }

  // Rate limit
  if (
    lower.includes("rate limit") ||
    lower.includes("rate_limit_exceeded") ||
    lower.includes("429")
  ) {
    return "Unfortunately, the Rate limit exceeded. Please try again in a few moments.";
  }

  // Authentication / invalid key
  if (
    lower.includes("auth") ||
    lower.includes("invalid_api_key") ||
    lower.includes("api_key") ||
    lower.includes("key expired") ||
    lower.includes("incorrect api key")
  ) {
    return "Authentication failed. Please check that your API keys are configured correctly.";
  }

  // If it's a nested python error dictionary/string, try to extract the inner message
  if (rawMessage.includes("Error code:")) {
    const match = rawMessage.match(/'message':\s*'([^']+)'/) || rawMessage.match(/"message":\s*"([^"]+)"/);
    if (match && match[1]) {
      return match[1];
    }
  }

  return rawMessage;
}

