import { NextRequest, NextResponse } from "next/server";
import { proxyBackend } from "@/lib/backend-proxy";

export const dynamic = "force-dynamic";

/** Create a price alert. Proxies to Python backend; demo fallback echoes. */
export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));

  const r = await proxyBackend<{
    alert: {
      id: string;
      symbol: string;
      condition: string;
      price: number;
      active: boolean;
      triggered: boolean;
      createdAt: number;
    };
  }>(
    `/api/trading/alerts`,
    { method: "POST", body: JSON.stringify(body) },
    3000
  );
  if (r.data) return NextResponse.json(r.data);

  // Demo fallback
  const { symbol, condition, price } = body;
  return NextResponse.json({
    alert: {
      id: `pa-${Date.now()}`,
      symbol,
      condition,
      price: parseFloat(price),
      active: true,
      triggered: false,
      createdAt: Date.now(),
    },
    demo: true,
  });
}
