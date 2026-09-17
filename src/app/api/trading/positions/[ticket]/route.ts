import { NextRequest, NextResponse } from "next/server";
import { proxyBackend } from "@/lib/backend-proxy";

export const dynamic = "force-dynamic";

/** Close a position by ticket. Proxies to Python backend; demo fallback simulates. */
export async function DELETE(
  _req: NextRequest,
  { params }: { params: Promise<{ ticket: string }> }
) {
  const { ticket } = await params;
  const ticketNum = parseInt(ticket);

  const r = await proxyBackend<{ ok: boolean; retcode?: number }>(
    `/api/trading/positions/${ticketNum}`,
    { method: "DELETE" },
    8000
  );
  if (r.data) return NextResponse.json(r.data);

  // Demo fallback
  return NextResponse.json({
    ok: true,
    demo: true,
    message: `Position #${ticket} closed (demo)`,
  });
}
