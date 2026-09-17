import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json({
    connected: false,
    demo: true,
    terminal: null,
    account: null,
    message: "MT5 not connected — running in simulation/demo mode",
  });
}
