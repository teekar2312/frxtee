import { NextRequest, NextResponse } from "next/server";
import { proxyBackend } from "@/lib/backend-proxy";

export const dynamic = "force-dynamic";

/** GET: fetch current AI config from backend */
export async function GET() {
  const r = await proxyBackend<{
    models: Record<string, string>;
    ai_min_confidence: number;
    auto_trade_min_confidence: number;
    active_provider: string;
    api_keys_set: Record<string, boolean>;
  }>(`/api/trading/ai/config`, {}, 3000);

  if (r.data) return NextResponse.json(r.data);
  return NextResponse.json({ demo: true });
}

/** POST: update AI config on backend (runtime, no restart) */
export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));

  const r = await proxyBackend<{
    ok: boolean;
    updated: string[];
    config: Record<string, unknown>;
  }>(`/api/trading/ai/config`,
    { method: "POST", body: JSON.stringify(body) },
    5000
  );
  if (r.data) return NextResponse.json(r.data);
  return NextResponse.json({ ok: false, demo: true, error: "Backend not connected" });
}
