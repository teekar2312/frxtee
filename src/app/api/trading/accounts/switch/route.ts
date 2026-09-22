import { NextRequest, NextResponse } from "next/server";
import { proxyBackend } from "@/lib/backend-proxy";
export const dynamic = "force-dynamic";
export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const r = await proxyBackend<any>(`/api/trading/accounts/switch`,
    { method: "POST", body: JSON.stringify(body) }, 15000);
  if (r.data) return NextResponse.json(r.data);
  return NextResponse.json({ ok: false, demo: true });
}
