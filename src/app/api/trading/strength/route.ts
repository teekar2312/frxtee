import { NextResponse } from "next/server";
import { proxyBackend } from "@/lib/backend-proxy";
export const dynamic = "force-dynamic";
export async function GET() {
  const r = await proxyBackend<any>(`/api/trading/strength`, {}, 5000);
  if (r.data) return NextResponse.json(r.data);
  return NextResponse.json({ demo: true });
}
