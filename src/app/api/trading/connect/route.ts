import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

// In production this would proxy to the Python MT5 backend (port 8000).
// Here we simulate the connect handshake.
export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const login = body?.login ?? "5012****";
  const server = body?.server ?? "FINEX-Real";
  await new Promise((r) => setTimeout(r, 900));
  return NextResponse.json({
    connected: true,
    demo: false,
    message: `Connected to ${server} as ${login}. MetaTrader 5 launched automatically.`,
    terminal: "C:\\Program Files\\FINEX MetaTrader 5\\terminal64.exe",
    account: { login, server, leverage: "1:500", currency: "USD" },
  });
}

export async function DELETE() {
  return NextResponse.json({ connected: false, demo: true, message: "Disconnected from MT5." });
}
