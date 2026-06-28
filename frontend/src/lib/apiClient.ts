import { toast } from 'sonner';

/**
 * Resilient wrapper around the native browser fetch API.
 * Automatically handles CORS/auth credentials, intercepts HTTP errors,
 * registers Sonner toast alert messages, and formats JSON results.
 */
export async function apiFetch<T>(url: string, options?: RequestInit): Promise<T> {
  let skipToast = false;
  let cleanHeaders: HeadersInit = {};
  
  if (options?.headers) {
    if (options.headers instanceof Headers) {
      skipToast = options.headers.get('X-Skip-Toast') === 'true' || options.headers.get('x-skip-toast') === 'true';
      const tempHeaders = new Headers(options.headers);
      tempHeaders.delete('X-Skip-Toast');
      tempHeaders.delete('x-skip-toast');
      cleanHeaders = tempHeaders;
    } else if (Array.isArray(options.headers)) {
      skipToast = options.headers.some(([k, v]) => k.toLowerCase() === 'x-skip-toast' && v === 'true');
      cleanHeaders = options.headers.filter(([k]) => k.toLowerCase() !== 'x-skip-toast');
    } else {
      const record = options.headers as Record<string, string>;
      skipToast = record['X-Skip-Toast'] === 'true' || record['x-skip-toast'] === 'true';
      const temp = { ...record };
      delete temp['X-Skip-Toast'];
      delete temp['x-skip-toast'];
      cleanHeaders = temp;
    }
  } else {
    cleanHeaders = options?.headers || {};
  }

  const mergedOptions: RequestInit = {
    ...options,
    headers: cleanHeaders,
    credentials: options?.credentials || 'include',
  };

  try {
    const response = await fetch(url, mergedOptions);

    if (!response.ok) {
      let errorMsg = `HTTP Error ${response.status}`;
      // Structured-detail codes that represent intentional throttle / soft
      // block (NOT a system failure). When matched, the toast uses warning
      // styling + longer duration + no "API Failure:" prefix, since calling
      // a deliberate rate-limit a "failure" misleads the user about whose
      // side has the problem.
      const THROTTLE_CODES = new Set(['rate_limited', 'decision_immutable']);
      let throttleCode: string | undefined;

      try {
        const errorData = await response.json();
        if (errorData && typeof errorData === 'object') {
          const detail = errorData.detail;
          // FastAPI HTTPException allows `detail` to be either a string
          // (legacy / most endpoints) or a structured object
          // (e.g., /approve 409 + /run-pipeline 429: {code, message, next_step}).
          if (detail && typeof detail === 'object') {
            const code = (detail as Record<string, unknown>).code;
            if (typeof code === 'string' && THROTTLE_CODES.has(code)) {
              throttleCode = code;
            }
            const parts = [
              (detail as Record<string, unknown>).message,
              (detail as Record<string, unknown>).next_step,
            ].filter(Boolean) as string[];
            errorMsg = parts.length > 0 ? parts.join(' - ') : JSON.stringify(detail);
          } else {
            errorMsg = detail || errorData.message || JSON.stringify(errorData);
          }
        }
      } catch {
        // Fallback to generic status text if response is not JSON
        if (response.statusText) {
          errorMsg = `${response.status}: ${response.statusText}`;
        }
      }

      if (throttleCode) {
        // Amber warning toast (not red error) + 8s duration so the user can
        // read the next_step (e.g. contact info in the rate-limit message).
        toast.warning(errorMsg, { duration: 8000 });
      } else if (!skipToast) {
        toast.error(`API Failure: ${errorMsg}`);
      }
      throw new Error(errorMsg);
    }

    if (response.status === 204) {
      return {} as T;
    }

    return (await response.json()) as T;
  } catch (error: unknown) {
    // Differentiate native fetch network errors from API response errors
    if (error instanceof TypeError && error.message.toLowerCase().includes('failed to fetch')) {
      const offlineMsg = "Network connection failed. The EM Copilot API appears to be offline.";
      toast.error(offlineMsg);
      throw new Error(offlineMsg, { cause: error });
    }

    // Re-throw so components can reset their loading state
    throw error;
  }
}
