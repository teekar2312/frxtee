import { NextResponse } from "next/server";
import { type LogEntry } from "@/lib/trading-data";
import { proxyBackend, jsonWithDemo } from "@/lib/backend-proxy";
import { DEMO_LOGS } from "@/lib/demo-logs";

export const dynamic = "force-dynamic";

export async function GET() {
  const r = await proxyBackend<{ logs: LogEntry[] }>(`/api/trading/logs`);
  if (r.data && r.data.logs.length > 0) {
    return NextResponse.json({ ...r.data, demo: false });
  }
  return jsonWithDemo({ logs: DEMO_LOGS }, false);
}
