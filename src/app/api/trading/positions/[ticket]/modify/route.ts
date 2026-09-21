import { NextRequest, NextResponse } from "next/server";
import { proxyBackend } from "@/lib/backend-proxy";

export const dynamic = "force-dynamic";

/** Modify SL/TP of an open position (trailing stop / break-even). */
export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ ticket: string }> }
) {
  const { ticket } = await params;
  const body = await req.json().catch(() => ({}));

  const r = await proxyBackend<{ ok: boolean; error?: string; sl?: number; tp?: number }>(
    `/api/trading/positions/${ticket}/modify`,
    { method: "POST", body: JSON.stringify(body) },
    8000
  );
  if (r.data) return NextResponse.json(r.data);

  return NextResponse.json({ ok: false, error: "Backend unavailable", demo: true });
}
