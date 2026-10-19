import { NextRequest, NextResponse } from "next/server";
import { proxyBackend } from "@/lib/backend-proxy";

export const dynamic = "force-dynamic";

/** Trigger ML model retraining. Proxies to Python backend; demo fallback simulates. */
export async function POST(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const symbol = searchParams.get("symbol") ?? "EURUSD";

  const r = await proxyBackend<{ ok: boolean; message: string }>(
    `/api/trading/ml/train?symbol=${symbol}`,
    { method: "POST" },
    60000 // training can take 10-60s depending on data size + CPU
  );
  if (r.data) return NextResponse.json(r.data);

  // Demo fallback
  return NextResponse.json({
    ok: false,
    demo: true,
    message: `Training failed for ${symbol} — backend not connected or timed out (60s)`,
  });
}
