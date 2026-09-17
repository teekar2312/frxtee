import { NextResponse } from "next/server";
import { genPositions, type Position } from "@/lib/trading-data";
import { proxyBackend, jsonWithDemo } from "@/lib/backend-proxy";

export const dynamic = "force-dynamic";

export async function GET() {
  const r = await proxyBackend<{ positions: Position[] }>(`/api/trading/positions`);
  if (r.data) return NextResponse.json({ ...r.data, demo: false });
  return jsonWithDemo({ positions: genPositions() }, false);
}
