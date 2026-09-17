/**
 * Backend proxy helper.
 *
 * Each `/api/trading/*` route tries to proxy to the Python FastAPI backend
 * (TRADING_BACKEND_URL, default http://127.0.0.1:8000). If the backend is
 * unreachable (e.g. dev sandbox, or not started on Windows yet), the route
 * falls back to demo data so the dashboard always works.
 */
import { NextRequest, NextResponse } from "next/server";

export const BACKEND_URL =
  process.env.TRADING_BACKEND_URL || "http://127.0.0.1:8000";

/** Probe result returned by the proxy. */
export interface ProxyResult<T> {
  data: T | null;
  proxied: boolean;
  status: number;
}

/**
 * Forward a request to the Python backend.
 *
 * @param path     backend path, e.g. "/api/trading/ticks"
 * @param init     fetch init (method, body, headers)
 * @param timeoutMs connection/read timeout (default 1500ms)
 */
export async function proxyBackend<T>(
  path: string,
  init: RequestInit = {},
  timeoutMs = 1500
): Promise<ProxyResult<T>> {
  const url = `${BACKEND_URL}${path}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      ...init,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...(init.headers as Record<string, string> | undefined),
      },
    });
    clearTimeout(timer);
    if (!res.ok) {
      return { data: null, proxied: false, status: res.status };
    }
    const data = (await res.json()) as T;
    return { data, proxied: true, status: 200 };
  } catch {
    clearTimeout(timer);
    // backend unreachable → caller falls back to demo data
    return { data: null, proxied: false, status: 0 };
  }
}

/** Convenience JSON response wrapper that tags `demo` based on proxy result. */
export function jsonWithDemo<T>(
  data: T,
  proxied: boolean,
  status = 200
): NextResponse {
  return NextResponse.json(
    { ...data, demo: !proxied },
    { status }
  );
}

/** Parse search params from a NextRequest into a backend query string. */
export function passthroughQuery(req: NextRequest): string {
  const { searchParams } = new URL(req.url);
  return searchParams.toString();
}
