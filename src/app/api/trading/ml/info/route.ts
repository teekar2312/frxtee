import { NextResponse } from "next/server";
import { proxyBackend } from "@/lib/backend-proxy";

export const dynamic = "force-dynamic";

/** Get ML model info. Proxies to Python backend; demo fallback if unreachable. */
export async function GET() {
  const r = await proxyBackend<{
    exists: boolean;
    version: string;
    train_acc: number | null;
    test_acc: number | null;
    symbol: string | null;
    trained_at: string | null;
    n_samples: number | null;
    demo?: boolean;
  }>(`/api/trading/ml/info`, {}, 5000);

  if (r.data) return NextResponse.json(r.data);

  // Demo fallback: no model
  return NextResponse.json({
    exists: false,
    version: "—",
    train_acc: null,
    test_acc: null,
    symbol: null,
    trained_at: null,
    n_samples: null,
    demo: true,
  });
}
