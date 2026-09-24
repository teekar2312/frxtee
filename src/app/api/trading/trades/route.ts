import { NextResponse } from "next/server";
import { proxyBackend } from "@/lib/backend-proxy";

export const dynamic = "force-dynamic";

/** Get trade history from DB. */
export async function GET() {
  const r = await proxyBackend<{ trades: any[] }>(`/api/trading/trades`, {}, 3000);
  if (r.data) return NextResponse.json(r.data);
  return NextResponse.json({ trades: [], demo: true });
}
