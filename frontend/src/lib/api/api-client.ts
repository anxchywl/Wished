import { env } from "@/lib/config/env";
import { useAuthStore } from "@/stores/auth-store";

type RequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
  accessToken?: string | null;
  /** internal flag: skip the refresh-retry loop for auth endpoints */
  _skipRefresh?: boolean;
};

const REQUEST_TIMEOUT_MS = 8_000;

/**
 * api request error
 */
export class ApiError extends Error {
  constructor(
    readonly message: string,
    readonly status: number,
    readonly payload: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * send api request
 */
export async function apiClient<TResponse>(
  path: string,
  options: RequestOptions = {},
): Promise<TResponse> {
  const { accessToken, _skipRefresh, ...fetchOptions } = options;
  const headers = new Headers(options.headers);
  const timeoutController = new AbortController();
  const timeoutId = globalThis.setTimeout(() => timeoutController.abort(), REQUEST_TIMEOUT_MS);

  if (options.body !== undefined && !headers.has("Content-Type")) {
    if (!(options.body instanceof FormData)) {
      headers.set("Content-Type", "application/json");
    }
  }
  if (accessToken && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  try {
    const response = await fetch(`${env.apiBaseUrl}${path}`, {
      cache: "no-store",
      credentials: "include",
      ...fetchOptions,
      headers,
      signal: fetchOptions.signal ?? timeoutController.signal,
      body:
        options.body === undefined
          ? undefined
          : options.body instanceof FormData
            ? options.body
            : JSON.stringify(options.body),
    });

    const payload = await parseResponse(response);

    if (!response.ok) {
      if (response.status === 401 && !_skipRefresh) {
        const refreshed = await _attemptRefresh();
        if (refreshed) {
          // retry original request once with the new access token
          return apiClient(path, {
            ...options,
            accessToken: refreshed,
            _skipRefresh: true,
          });
        }
        useAuthStore.getState().setAccessToken(null);
      } else if (response.status === 401) {
        useAuthStore.getState().setAccessToken(null);
      }
      throw new ApiError(response.statusText || "API request failed", response.status, payload);
    }

    return payload as TResponse;
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError("API request timed out", 408, null);
    }

    throw err;
  } finally {
    globalThis.clearTimeout(timeoutId);
  }
}

/**
 * attempt a silent token refresh using the httpOnly cookie.
 * returns the new access token on success, null on failure.
 */
async function _attemptRefresh(): Promise<string | null> {
  try {
    const response = await fetch(`${env.apiBaseUrl}/auth/refresh`, {
      method: "POST",
      credentials: "include",
      cache: "no-store",
    });
    if (!response.ok) return null;
    const data = (await response.json()) as { access_token: string };
    useAuthStore.getState().setAccessToken(data.access_token);
    return data.access_token;
  } catch {
    return null;
  }
}

/**
 * parse api response
 */
async function parseResponse(response: Response): Promise<unknown> {
  if (response.status === 204) {
    return null;
  }

  const contentType = response.headers.get("Content-Type") ?? "";

  if (contentType.includes("application/json")) {
    return response.json();
  }

  return response.text();
}
