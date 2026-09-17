import { NextResponse } from "next/server";
import { proxyBackend } from "@/lib/backend-proxy";

export const dynamic = "force-dynamic";

export async function GET() {
  const r = await proxyBackend<{
    connected: boolean;
    demo: boolean;
    terminal: string | null;
    account: { login: string; server: string; leverage: string; currency: string; balance: number; equity: number } | null;
    message: string;
  }>(`/api/trading/status`);

  if (r.data) return NextResponse.json(r.data);

  return NextResponse.json({
    connected: false,
    demo: true,
    terminal: null,
    account: null,
    message: "MT5 not connected — running in simulation/demo mode",
  });
}
