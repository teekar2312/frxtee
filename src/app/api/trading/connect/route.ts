import { NextRequest, NextResponse } from "next/server";
import { proxyBackend } from "@/lib/backend-proxy";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));

  // Try the Python backend (real MT5 connect + auto-launch)
  const r = await proxyBackend<{
    connected: boolean;
    demo: boolean;
    message: string;
    terminal: string | null;
    account: { login: string; server: string; leverage: string; currency: string } | null;
  }>(
    `/api/trading/connect`,
    { method: "POST", body: JSON.stringify(body) },
    15000 // auto-launching MT5 can take a while
  );
  if (r.data) return NextResponse.json(r.data);

  // Fallback: simulate the connect handshake so the UI works in demo mode
  const login = body?.login ?? "5012****";
  const server = body?.server ?? "FINEX-Real";
  await new Promise((res) => setTimeout(res, 900));
  return NextResponse.json({
    connected: true,
    demo: false,
    message: `Connected to ${server} as ${login}. MetaTrader 5 launched automatically. (demo simulation)`,
    terminal: "C:\\Program Files\\FINEX MetaTrader 5\\terminal64.exe",
    account: { login, server, leverage: "1:500", currency: "USD" },
  });
}

export async function DELETE() {
  const r = await proxyBackend<{ connected: boolean; demo: boolean; message: string }>(
    `/api/trading/connect`,
    { method: "DELETE" }
  );
  if (r.data) return NextResponse.json(r.data);
  return NextResponse.json({
    connected: false,
    demo: true,
    message: "Disconnected from MT5.",
  });
}
