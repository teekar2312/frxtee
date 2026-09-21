import { NextResponse } from "next/server";
import { proxyBackend } from "@/lib/backend-proxy";

export const dynamic = "force-dynamic";

/** Export trades as CSV. */
export async function GET() {
  const r = await proxyBackend<{ trades: any[]; csv: string }>(
    `/api/trading/export`, {}, 5000
  );
  if (r.data && r.data.csv) {
    return new NextResponse(r.data.csv, {
      headers: {
        "Content-Type": "text/csv",
        "Content-Disposition": "attachment; filename=trades.csv",
      },
    });
  }
  return NextResponse.json({ error: "Export unavailable", demo: true });
}
