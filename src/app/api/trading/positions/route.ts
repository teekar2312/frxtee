import { NextResponse } from "next/server";
import { genPositions } from "@/lib/trading-data";

export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json({ positions: genPositions(), demo: true });
}
