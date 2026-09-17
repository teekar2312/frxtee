"use client";

import * as React from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { Bell, BellRing, Mail, Plus, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { fmtPrice, TRADING_PAIRS, type PriceAlert } from "@/lib/trading-data";
import { useTradingStore } from "@/lib/trading-store";
import { BadgeTone, SectionHeader, SwitchRow } from "./primitives";

export function AlertsView() {
  const { emailEnabled, emailTo, setEmailEnabled, setEmailTo } = useTradingStore();
  const [alerts, setAlerts] = React.useState<PriceAlert[]>([
    {
      id: "a1",
      symbol: "EURUSD",
      condition: "above",
      price: 1.088,
      active: true,
      createdAt: new Date(Date.now() - 3600000).toISOString(),
      triggered: false,
    },
    {
      id: "a2",
      symbol: "XAUUSD",
      condition: "cross_up",
      price: 2350,
      active: true,
      createdAt: new Date(Date.now() - 7200000).toISOString(),
      triggered: true,
    },
  ]);

  const [symbol, setSymbol] = React.useState("EURUSD");
  const [condition, setCondition] = React.useState<PriceAlert["condition"]>("above");
  const [price, setPrice] = React.useState("");

  function add() {
    const p = parseFloat(price);
    if (!p || !symbol) {
      toast.error("Enter symbol and price");
      return;
    }
    setAlerts((a) => [
      {
        id: `a${Date.now()}`,
        symbol,
        condition,
        price: p,
        active: true,
        createdAt: new Date().toISOString(),
        triggered: false,
      },
      ...a,
    ]);
    toast.success(`Alert set: ${symbol} ${condition} ${p}`);
    setPrice("");
  }

  function toggle(id: string) {
    setAlerts((a) => a.map((x) => (x.id === id ? { ...x, active: !x.active } : x)));
  }
  function remove(id: string) {
    setAlerts((a) => a.filter((x) => x.id !== id));
  }

  function sendTestEmail() {
    toast.success(`Test email sent to ${emailTo || "(not configured)"}`);
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
      <Card className="p-3">
        <SectionHeader
          title="Price Alerts"
          desc={`${alerts.filter((a) => a.active).length} active · ${alerts.filter((a) => a.triggered).length} triggered`}
          icon={BellRing}
        />
        <div className="grid grid-cols-12 gap-2 mb-3">
          <div className="col-span-4">
            <Label className="text-[11px] text-muted-foreground">Symbol</Label>
            <Select value={symbol} onValueChange={setSymbol}>
              <SelectTrigger className="h-8 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TRADING_PAIRS.map((p) => (
                  <SelectItem key={p.symbol} value={p.symbol} className="text-xs">
                    {p.display}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="col-span-4">
            <Label className="text-[11px] text-muted-foreground">Condition</Label>
            <Select value={condition} onValueChange={(v) => setCondition(v as PriceAlert["condition"])}>
              <SelectTrigger className="h-8 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="above" className="text-xs">Above</SelectItem>
                <SelectItem value="below" className="text-xs">Below</SelectItem>
                <SelectItem value="cross_up" className="text-xs">Cross Up</SelectItem>
                <SelectItem value="cross_down" className="text-xs">Cross Down</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="col-span-3">
            <Label className="text-[11px] text-muted-foreground">Price</Label>
            <Input
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              placeholder="0.0000"
              className="h-8 text-xs"
              type="number"
            />
          </div>
          <div className="col-span-1 flex items-end">
            <Button size="sm" className="h-8 w-full p-0" onClick={add}>
              <Plus className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="max-h-72 overflow-y-auto scroll-thin -mx-1 space-y-1">
          {alerts.length === 0 ? (
            <div className="text-center text-xs text-muted-foreground py-6">
              No alerts — create one above
            </div>
          ) : (
            alerts.map((a) => (
              <div
                key={a.id}
                className={cn(
                  "flex items-center gap-2 rounded-md border p-2",
                  a.triggered && "border-warning/40 bg-warning/5"
                )}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-sm font-medium">{a.symbol}</span>
                    <BadgeTone tone="neutral">{a.condition.replace("_", " ")}</BadgeTone>
                    <span className="text-sm font-semibold tnum">
                      {fmtPrice(a.price, a.symbol.includes("JPY") ? 3 : 5)}
                    </span>
                    {a.triggered ? <BadgeTone tone="warn">triggered</BadgeTone> : null}
                  </div>
                  <div className="text-[10px] text-muted-foreground">
                    {new Date(a.createdAt).toLocaleString("en-GB")}
                  </div>
                </div>
                <Switch checked={a.active} onCheckedChange={() => toggle(a.id)} />
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 text-danger"
                  onClick={() => remove(a.id)}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            ))
          )}
        </div>
      </Card>

      <div className="space-y-3">
        <Card className="p-3">
          <SectionHeader title="Email Notifications" icon={Mail} />
          <SwitchRow
            label="Enable email alerts"
            desc="Receive trade, alert & risk notifications"
            checked={emailEnabled}
            onChange={setEmailEnabled}
          />
          <div className="mt-2">
            <Label className="text-[11px] text-muted-foreground">Recipient email</Label>
            <Input
              value={emailTo}
              onChange={(e) => setEmailTo(e.target.value)}
              placeholder="trader@example.com"
              className="h-8 text-xs"
              type="email"
            />
          </div>
          <Button variant="outline" size="sm" className="h-8 mt-2" onClick={sendTestEmail}>
            <Mail className="h-3.5 w-3.5 mr-1" /> Send test email
          </Button>
          <div className="mt-3 space-y-1">
            <SwitchRow label="Trade open / close" checked={true} onChange={() => {}} />
            <SwitchRow label="Daily risk limit breach" checked={true} onChange={() => {}} />
            <SwitchRow label="Price alert triggered" checked={true} onChange={() => {}} />
            <SwitchRow label="High-impact news (15min)" checked={false} onChange={() => {}} />
            <SwitchRow label="AI signal (confidence > 80%)" checked={true} onChange={() => {}} />
          </div>
        </Card>

        <Card className="p-3">
          <SectionHeader title="Recent Notifications" icon={Bell} />
          <div className="space-y-1.5 max-h-60 overflow-y-auto scroll-thin">
            {recent.map((n) => (
              <div key={n.id} className="flex items-start gap-2 rounded-md border p-2">
                <BadgeTone tone={n.tone}>{n.tag}</BadgeTone>
                <div className="flex-1 min-w-0">
                  <div className="text-xs">{n.msg}</div>
                  <div className="text-[10px] text-muted-foreground">{n.ts}</div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

const recent = [
  { id: "1", tag: "trade", tone: "up" as const, msg: "OPEN BUY EURUSD 0.10 @ 1.08642 (AI:auto)", ts: "2m ago" },
  { id: "2", tag: "alert", tone: "warn" as const, msg: "XAUUSD crossed above 2350.0", ts: "12m ago" },
  { id: "3", tag: "risk", tone: "down" as const, msg: "Daily risk usage 2.1% / 3.0%", ts: "31m ago" },
  { id: "4", tag: "news", tone: "neutral" as const, msg: "High-impact: US CPI in 15 minutes", ts: "44m ago" },
  { id: "5", tag: "ai", tone: "up" as const, msg: "AI signal STRONG BUY GBPJPY (84% confidence)", ts: "1h ago" },
];
