"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useTheme } from "next-themes";
import { toast } from "sonner";
import {
  Activity,
  AlertTriangle,
  Bell,
  Bot,
  Brain,
  CandlestickChart,
  Check,
  FlaskConical,
  Gauge,
  LayoutDashboard,
  Moon,
  Newspaper,
  Plug,
  Rows3,
  ScrollText,
  Settings,
  Sun,
  TrendingUp,
  Zap,
} from "lucide-react";
import { useTradingStore, type Density } from "@/lib/trading-store";
import dynamic from "next/dynamic";
import { TickerTape } from "@/components/trading/ticker-tape";
import { SessionClock } from "@/components/trading/session-clock";

// Code-split heavy views — only loaded when navigated to (smaller initial bundle)
const DashboardView = dynamic(() => import("@/components/trading/dashboard-view").then(m => ({ default: m.DashboardView })), { loading: () => <ViewSkeleton /> });
const TradingView = dynamic(() => import("@/components/trading/trading-view").then(m => ({ default: m.TradingView })), { loading: () => <ViewSkeleton /> });
const AIEngineView = dynamic(() => import("@/components/trading/ai-engine-view").then(m => ({ default: m.AIEngineView })), { loading: () => <ViewSkeleton /> });
const IndicatorsView = dynamic(() => import("@/components/trading/indicators-view").then(m => ({ default: m.IndicatorsView })), { loading: () => <ViewSkeleton /> });
const RiskView = dynamic(() => import("@/components/trading/risk-view").then(m => ({ default: m.RiskView })), { loading: () => <ViewSkeleton /> });
const NewsView = dynamic(() => import("@/components/trading/news-view").then(m => ({ default: m.NewsView })), { loading: () => <ViewSkeleton /> });
const BacktestView = dynamic(() => import("@/components/trading/backtest-view").then(m => ({ default: m.BacktestView })), { loading: () => <ViewSkeleton /> });
const AlertsView = dynamic(() => import("@/components/trading/alerts-view").then(m => ({ default: m.AlertsView })), { loading: () => <ViewSkeleton /> });
const LogsView = dynamic(() => import("@/components/trading/logs-view").then(m => ({ default: m.LogsView })), { loading: () => <ViewSkeleton /> });
const SettingsView = dynamic(() => import("@/components/trading/settings-view").then(m => ({ default: m.SettingsView })), { loading: () => <ViewSkeleton /> });

function ViewSkeleton() {
  return (
    <div className="space-y-3">
      <div className="h-16 w-full rounded-md bg-muted animate-pulse" />
      <div className="grid grid-cols-3 gap-3">
        <div className="h-40 rounded-md bg-muted animate-pulse" />
        <div className="h-40 rounded-md bg-muted animate-pulse" />
        <div className="h-40 rounded-md bg-muted animate-pulse" />
      </div>
    </div>
  );
}

type ViewId =
  | "dashboard"
  | "trading"
  | "ai"
  | "indicators"
  | "risk"
  | "news"
  | "backtest"
  | "alerts"
  | "logs"
  | "settings";

const NAV: { id: ViewId; label: string; icon: any }[] = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "trading", label: "Trading", icon: CandlestickChart },
  { id: "ai", label: "AI Engine", icon: Brain },
  { id: "indicators", label: "Indicators", icon: Activity },
  { id: "risk", label: "Risk Mgmt", icon: Gauge },
  { id: "news", label: "News", icon: Newspaper },
  { id: "backtest", label: "Backtest", icon: FlaskConical },
  { id: "alerts", label: "Alerts", icon: Bell },
  { id: "logs", label: "Logs", icon: ScrollText },
  { id: "settings", label: "Settings", icon: Settings },
];

export default function Page() {
  const [view, setView] = React.useState<ViewId>("dashboard");
  const { theme, setTheme } = useTheme();
  const mt5Connected = useTradingStore((s) => s.mt5Connected);
  const demoMode = useTradingStore((s) => s.demoMode);
  const autoTrade = useTradingStore((s) => s.autoTradeMode);
  const aiProvider = useTradingStore((s) => s.aiProvider);
  const density = useTradingStore((s) => s.density);
  const setDensity = useTradingStore((s) => s.setDensity);
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => setMounted(true), []);

  // Apply density to <html> + persist. The store already initialises from
  // localStorage (safe for SSR), so this effect just keeps the DOM & storage
  // in sync when density changes.
  React.useEffect(() => {
    document.documentElement.dataset.density = density;
    try {
      localStorage.setItem("zenitrade-density", density);
    } catch {
      /* ignore */
    }
  }, [density]);

  return (
    <div className="min-h-screen flex flex-col bg-background">
      {/* Header */}
      <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/70">
        <div className="flex items-center gap-3 px-3 h-12">
          <div className="flex items-center gap-2">
            <div className="h-7 w-7 rounded-md bg-primary grid place-items-center text-primary-foreground">
              <TrendingUp className="h-4 w-4" />
            </div>
            <div className="leading-tight">
              <div className="text-sm font-semibold">ZeniTrade AI</div>
              <div className="text-[10px] text-muted-foreground -mt-0.5">
                FINEX · MT5 Terminal
              </div>
            </div>
          </div>

          <div className="hidden md:flex items-center gap-2 ml-2">
            <StatusPill
              ok={mt5Connected}
              okLabel="MT5 LIVE"
              offLabel="DEMO"
              icon={Plug}
            />
            {autoTrade ? (
              <span className="inline-flex items-center gap-1 rounded-md border border-success/30 bg-success/10 px-2 py-1 text-[10px] font-medium text-success">
                <Bot className="h-3 w-3" /> AI AUTO
              </span>
            ) : null}
            <span className="inline-flex items-center gap-1 rounded-md border px-2 py-1 text-[10px] font-medium text-muted-foreground">
              <Zap className="h-3 w-3" /> AI: {aiProvider.toUpperCase()}
            </span>
          </div>

          <div className="ml-auto flex items-center gap-2">
            <SessionClock />
            <DensityMenu density={density} onChange={setDensity} mounted={mounted} />
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
              title="Toggle theme"
            >
              {mounted && theme === "dark" ? (
                <Sun className="h-4 w-4" />
              ) : (
                <Moon className="h-4 w-4" />
              )}
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 relative"
              onClick={() => setView("alerts")}
            >
              <Bell className="h-4 w-4" />
              <span className="absolute top-1 right-1 h-1.5 w-1.5 rounded-full bg-danger" />
            </Button>
          </div>
        </div>
        <TickerTape />
      </header>

      {/* Body */}
      <div className="flex-1 flex">
        {/* Sidebar */}
        <nav className="w-14 md:w-44 shrink-0 border-r bg-sidebar/50 sticky top-[88px] self-start h-[calc(100vh-88px)] overflow-y-auto scroll-thin">
          <div className="p-1.5 space-y-0.5">
            {NAV.map((n) => {
              const active = view === n.id;
              const Icon = n.icon;
              return (
                <button
                  key={n.id}
                  onClick={() => setView(n.id)}
                  className={cn(
                    "w-full flex items-center gap-2 rounded-md px-2 py-2 text-sm transition-colors",
                    active
                      ? "bg-primary text-primary-foreground font-medium"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  )}
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  <span className="hidden md:inline truncate">{n.label}</span>
                </button>
              );
            })}
          </div>
          <div className="px-2 py-2 mt-2 border-t hidden md:block">
            <div className="text-[9px] uppercase text-muted-foreground mb-1">
              Risk Status
            </div>
            <div className="flex items-center gap-1.5 text-[11px]">
              <AlertTriangle className="h-3 w-3 text-success" />
              <span>Healthy · 0.8% / 3%</span>
            </div>
          </div>
        </nav>

        {/* Main */}
        <main className="flex-1 min-w-0 p-3">
          <ViewTitle view={view} />
          <View view={view} />
        </main>
      </div>

      {/* Sticky footer */}
      <footer className="mt-auto border-t bg-card/60 backdrop-blur">
        <div className="flex items-center gap-3 px-3 h-8 text-[10px] text-muted-foreground">
          <span className="flex items-center gap-1">
            <span
              className={cn(
                "h-1.5 w-1.5 rounded-full",
                mt5Connected ? "bg-success pulse-dot" : "bg-warning"
              )}
            />
            {mt5Connected ? "MT5 connected" : "Demo mode (no live broker)"}
          </span>
          <span className="hidden sm:inline">·</span>
          <span className="hidden sm:inline">FINEX Indonesia · 1:500 · spread from 0.5p</span>
          <span className="hidden md:inline">·</span>
          <span className="hidden md:inline">Python 3.14 · MT5 · AI: Z.AI / Groq / Google / Local</span>
          <span className="ml-auto">
            ⚠ Trading FX involves substantial risk — for educational/demo use.
          </span>
        </div>
      </footer>
    </div>
  );
}

function StatusPill({
  ok,
  okLabel,
  offLabel,
  icon: Icon,
}: {
  ok: boolean;
  okLabel: string;
  offLabel: string;
  icon: any;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-2 py-1 text-[10px] font-medium",
        ok
          ? "border-success/30 bg-success/10 text-success"
          : "border-warning/30 bg-warning/10 text-warning"
      )}
    >
      <Icon className="h-3 w-3" />
      {ok ? okLabel : offLabel}
    </span>
  );
}

const DENSITY_OPTIONS: {
  id: Density;
  label: string;
  desc: string;
}[] = [
  { id: "dense", label: "Dense", desc: "Maksimal data di layar" },
  { id: "compact", label: "Compact", desc: "Seimbang" },
  { id: "minimal", label: "Minimal", desc: "Legah & mudah dibaca" },
];

function DensityMenu({
  density,
  onChange,
  mounted,
}: {
  density: Density;
  onChange: (d: Density) => void;
  mounted: boolean;
}) {
  const active = DENSITY_OPTIONS.find((o) => o.id === density);
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="h-8 gap-1.5 px-2 text-xs"
          title="Display density"
        >
          <Rows3 className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">
            {mounted ? (active?.label ?? "Compact") : "Compact"}
          </span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel className="text-[11px] text-muted-foreground">
          Display density
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {DENSITY_OPTIONS.map((o) => (
          <DropdownMenuItem
            key={o.id}
            onClick={() => onChange(o.id)}
            className="flex items-start gap-2 py-1.5"
          >
            <Check
              className={cn(
                "h-3.5 w-3.5 mt-0.5 shrink-0",
                density === o.id ? "opacity-100" : "opacity-0"
              )}
            />
            <div className="min-w-0">
              <div className="text-xs font-medium leading-tight">{o.label}</div>
              <div className="text-[10px] text-muted-foreground leading-tight">
                {o.desc}
              </div>
            </div>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function ViewTitle({ view }: { view: ViewId }) {
  const titles: Record<ViewId, { t: string; d: string }> = {
    dashboard: { t: "Dashboard", d: "Overview · monitoring & operational" },
    trading: { t: "Trading", d: "Pairs · timeframes · sessions · order ticket" },
    ai: { t: "AI Engine", d: "ML analysis & multi-provider inference" },
    indicators: { t: "Technical Indicators", d: "30 indicators · auto or manual selection" },
    risk: { t: "Risk Management", d: "Money management · trailing · position sizing" },
    news: { t: "News", d: "Finnhub · MARKETAUX · economic calendar" },
    backtest: { t: "Backtesting", d: "Historical strategy simulation" },
    alerts: { t: "Alerts & Notifications", d: "Price alerts · email notifications" },
    logs: { t: "Logs", d: "System · error · trade logs" },
    settings: { t: "Settings", d: "MT5 connection · broker · API keys · theme" },
  };
  const x = titles[view];
  return (
    <div className="mb-3">
      <h1 className="text-base font-semibold leading-tight">{x.t}</h1>
      <p className="text-[11px] text-muted-foreground leading-tight">{x.d}</p>
    </div>
  );
}

function View({ view }: { view: ViewId }) {
  switch (view) {
    case "dashboard":
      return <DashboardView />;
    case "trading":
      return <TradingView />;
    case "ai":
      return <AIEngineView />;
    case "indicators":
      return <IndicatorsView />;
    case "risk":
      return <RiskView />;
    case "news":
      return <NewsView />;
    case "backtest":
      return <BacktestView />;
    case "alerts":
      return <AlertsView />;
    case "logs":
      return <LogsView />;
    case "settings":
      return <SettingsView />;
    default:
      return <DashboardView />;
  }
}
