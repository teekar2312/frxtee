import { NextRequest, NextResponse } from "next/server";
import { proxyBackend, passthroughQuery } from "@/lib/backend-proxy";
export const dynamic = "force-dynamic";
export async function GET(req: NextRequest) {
  const qs = passthroughQuery(req);
  const r = await proxyBackend<any>(`/api/trading/tax-report?${qs}`, {}, 5000);
  if (r.data) return NextResponse.json(r.data);
  return NextResponse.json({ demo: true });
}
