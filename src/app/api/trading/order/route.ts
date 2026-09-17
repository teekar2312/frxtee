import { NextRequest, NextResponse } from "next/server";
import { proxyBackend } from "@/lib/backend-proxy";

export const dynamic = "force-dynamic";

/** Place a market order. Proxies to Python backend; demo fallback simulates. */
export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));

  const r = await proxyBackend<{
    ok: boolean;
    ticket?: number;
    price?: number;
    volume?: number;
    error?: string;
  }>(
    `/api/trading/order`,
    { method: "POST", body: JSON.stringify(body) },
    8000
  );
  if (r.data) return NextResponse.json(r.data);

  // Demo fallback: simulate a successful order
  const { symbol, side, volume } = body;
  return NextResponse.json({
    ok: true,
    ticket: 5000000 + Math.floor(Math.random() * 9999),
    price: side === "BUY" ? 1.0865 : 1.0864,
    volume: volume ?? 0.1,
    demo: true,
    message: `Order accepted (demo): ${side} ${symbol} ${volume ?? 0.1} lot`,
  });
}
