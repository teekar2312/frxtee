import { NextRequest, NextResponse } from "next/server";
import { proxyBackend } from "@/lib/backend-proxy";

export const dynamic = "force-dynamic";

/** Partially close a position (scale-out). Body: { volume: 0.05 }. */
export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ ticket: string }> }
) {
  const { ticket } = await params;
  const body = await req.json().catch(() => ({}));

  const r = await proxyBackend<{ ok: boolean; error?: string; pnl?: number }>(
    `/api/trading/positions/${ticket}/partial`,
    { method: "POST", body: JSON.stringify(body) },
    8000
  );
  if (r.data) return NextResponse.json(r.data);

  return NextResponse.json({ ok: false, error: "Backend unavailable", demo: true });
}
