import { toast } from 'sonner';

/**
 * Resilient wrapper around the native browser fetch API.
 * Automatically handles CORS/auth credentials, intercepts HTTP errors,
 * registers Sonner toast alert messages, and formats JSON results.
 */
export async function apiFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const mergedOptions: RequestInit = {
    ...options,
    credentials: options?.credentials || 'include',
  };

  try {
    const response = await fetch(url, mergedOptions);

    if (!response.ok) {
      let errorMsg = `HTTP Error ${response.status}`;
      try {
        const errorData = await response.json();
        if (errorData && typeof errorData === 'object') {
          errorMsg = errorData.detail || errorData.message || JSON.stringify(errorData);
        }
      } catch {
        // Fallback to generic status text if response is not JSON
        if (response.statusText) {
          errorMsg = `${response.status}: ${response.statusText}`;
        }
      }

      toast.error(`API Failure: ${errorMsg}`);
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
