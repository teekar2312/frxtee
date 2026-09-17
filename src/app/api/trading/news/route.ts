import { NextResponse } from "next/server";
import { type NewsItem } from "@/lib/trading-data";
import { proxyBackend, jsonWithDemo } from "@/lib/backend-proxy";
import { DEMO_NEWS } from "@/lib/demo-news";

export const dynamic = "force-dynamic";

export async function GET() {
  const r = await proxyBackend<{ news: NewsItem[]; calendar: NewsItem[] }>(
    `/api/trading/news`
  );
  if (r.data) return NextResponse.json({ ...r.data, demo: false });
  return jsonWithDemo({ news: DEMO_NEWS, calendar: [] }, false);
}
