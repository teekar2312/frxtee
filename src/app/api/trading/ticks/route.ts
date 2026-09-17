import { NextRequest, NextResponse } from "next/server";
import { genPriceTicks, type PriceTick } from "@/lib/trading-data";
import { proxyBackend, jsonWithDemo, passthroughQuery } from "@/lib/backend-proxy";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const qs = passthroughQuery(req);
  const r = await proxyBackend<{ ts: number; ticks: PriceTick[] }>(
    `/api/trading/ticks${qs ? "?" + qs : ""}`
  );
  if (r.data) {
    return NextResponse.json({ ...r.data, demo: false });
  }
  return jsonWithDemo({ ts: Date.now(), ticks: genPriceTicks() }, false);
}
