"use client";

import * as React from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Slider } from "@/components/ui/slider";
import { useTheme } from "next-themes";
import { toast } from "sonner";
import {
  CheckCircle2,
  Cpu,
  KeyRound,
  Link2,
  Moon,
  Plug,
  Settings as SettingsIcon,
  Sun,
  Terminal,
  Unplug,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { BROKER_SPEC } from "@/lib/trading-data";
import { useTradingStore } from "@/lib/trading-store";
import { BadgeTone, SectionHeader, StatTile, SwitchRow } from "./primitives";

export function SettingsView() {
  const { theme, setTheme } = useTheme();
  const store = useTradingStore();
  const { mt5Connected, setMt5Connected, keys, setKey } = store;

  // Sync AI config from backend on mount
  React.useEffect(() => {
    fetch("/api/trading/ai/config")
      .then((r) => r.json())
      .then((d) => {
        if (d.models) {
          for (const [provider, model] of Object.entries(d.models)) {
            if (model && store.aiModels[provider] !== model) {
              store.setAiModel(provider, model as string);
            }
          }
        }
        if (d.ai_min_confidence != null) {
          store.setAiMinConfidence(d.ai_min_confidence);
        }
        if (d.auto_trade_min_confidence != null) {
          store.setAutoTradeMinConfidence(d.auto_trade_min_confidence);
        }
        // sync ollama context window size (prevents local AI OOM)
        if (d.ollama_num_ctx != null) {
          useTradingStore.setState({ ollamaNumCtx: d.ollama_num_ctx });
        }
        // sync ollama timeout (local models on CPU can be slow)
        if (d.ollama_timeout != null) {
          useTradingStore.setState({ ollamaTimeout: d.ollama_timeout });
        }
        // sync auto-trade mode from backend
        if (d.auto_trade_mode != null) {
          store.setAutoTradeMode(d.auto_trade_mode);
        }
        // sync sessions + strategy from backend.
        // NOTE: sessions are now pushed to backend immediately when toggled
        // in trading-view.tsx, so this sync is effectively a no-op in
        // practice (frontend already matches backend). It only matters
        // for first-run (no localStorage) or cross-device sync.
        if (d.active_sessions != null) {
          const sessions = d.active_sessions.split(",").filter((s: string) => s.trim());
          if (sessions.length > 0) {
            useTradingStore.setState({ sessions });
          }
        }
        if (d.close_at_session_end != null) {
          useTradingStore.setState({ closeAtSessionEnd: !!d.close_at_session_end });
        }
        if (d.trading_strategy != null) {
          store.setTradingStrategy(d.trading_strategy);
        }
        // sync risk management settings from backend
        if (d.risk_per_trade_pct != null) {
          useTradingStore.setState({ riskPerTrade: d.risk_per_trade_pct });
        }
        if (d.stop_loss_pips != null) {
          useTradingStore.setState({ stopLossPips: d.stop_loss_pips });
        }
        if (d.rr_ratio != null) {
          useTradingStore.setState({ rrRatio: d.rr_ratio });
        }
        if (d.max_open_positions != null) {
          useTradingStore.setState({ maxOpenPositions: d.max_open_positions });
        }
        if (d.daily_risk_limit_pct != null) {
          useTradingStore.setState({ dailyRiskLimit: d.daily_risk_limit_pct });
        }
        if (d.daily_target_pct != null) {
          useTradingStore.setState({ dailyTarget: d.daily_target_pct });
        }
        if (d.avoid_high_impact_news != null) {
          useTradingStore.setState({ avoidNews: !!d.avoid_high_impact_news });
        }
      })
      .catch(() => {});
  }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  // Push AI config changes to backend (called when user edits model/confidence)
  const pushAiConfig = React.useCallback(async () => {
    try {
      await fetch("/api/trading/ai/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          models: store.aiModels,
          ai_min_confidence: store.aiMinConfidence,
          auto_trade_min_confidence: store.autoTradeMinConfidence,
          active_provider: store.aiProvider,
          auto_trade_mode: store.autoTradeMode,
          auto_trade_symbols: store.symbols.join(","),
          active_sessions: store.sessions.join(","),
          close_at_session_end: store.closeAtSessionEnd,
          trading_strategy: store.tradingStrategy,
          ollama_num_ctx: store.ollamaNumCtx,
          ollama_timeout: store.ollamaTimeout,
          // risk management settings — synced so backend uses UI values,
          // not frozen .env defaults
          risk_per_trade_pct: store.riskPerTrade,
          stop_loss_pips: store.stopLossPips,
          rr_ratio: store.rrRatio,
          max_open_positions: store.maxOpenPositions,
          daily_risk_limit_pct: store.dailyRiskLimit,
          daily_target_pct: store.dailyTarget,
          avoid_high_impact_news: store.avoidNews,
        }),
      });
    } catch {
      // backend not running — config saved locally only
    }
  }, [store.aiModels, store.aiMinConfidence, store.autoTradeMinConfidence,
      store.aiProvider, store.autoTradeMode, store.symbols,
      store.sessions, store.closeAtSessionEnd, store.tradingStrategy,
      store.ollamaNumCtx, store.ollamaTimeout,
      store.riskPerTrade, store.stopLossPips, store.rrRatio,
      store.maxOpenPositions, store.dailyRiskLimit, store.dailyTarget,
      store.avoidNews]);
  const [login, setLogin] = React.useState("");
  const [server, setServer] = React.useState("FINEX-Real");
  const [password, setPassword] = React.useState("");
  const [terminal, setTerminal] = React.useState(
    "C:\\Program Files\\FINEX MetaTrader 5\\terminal64.exe"
  );
  const [connecting, setConnecting] = React.useState(false);
  const [autoLaunch, setAutoLaunch] = React.useState(true);

  // Auto-fill from backend status on mount (reads .env values)
  React.useEffect(() => {
    fetch("/api/trading/status")
      .then((r) => r.json())
      .then((d) => {
        if (d.account) {
          setLogin(String(d.account.login ?? ""));
          setServer(d.account.server ?? "FINEX-Real");
        }
        // sync terminal path from backend (.env MT5_TERMINAL_PATH)
        if (d.terminal) {
          setTerminal(d.terminal);
        }
        if (d.connected) {
          setMt5Connected(true);
          useTradingStore.setState({ demoMode: false });
        }
      })
      .catch(() => {});
  }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  async function connect() {
    if (!login || !password || !server) {
      toast.error("Login, password, dan server harus diisi");
      return;
    }
    setConnecting(true);
    try {
      const r = await fetch("/api/trading/connect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ login, password, server, autoLaunch, terminal }),
      });
      const d = await r.json();
      if (d.connected) {
        setMt5Connected(true);
        useTradingStore.setState({ demoMode: false });
        toast.success(d.message);
      } else {
        toast.error(d.message || d.error || "Connection failed");
      }
    } catch {
      toast.error("Connection failed — backend not running?");
    } finally {
      setConnecting(false);
    }
  }

  function disconnect() {
    fetch("/api/trading/connect", { method: "DELETE" });
    setMt5Connected(false);
    useTradingStore.setState({ demoMode: true });
    toast.info("Disconnected — demo mode active");
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
      {/* MT5 connection */}
      <Card className="p-3">
        <SectionHeader
          title="MetaTrader 5 Connection"
          desc="FINEX Indonesia · auto-launch supported"
          icon={Plug}
          right={
            mt5Connected ? (
              <BadgeTone tone="up">
                <CheckCircle2 className="inline h-3 w-3 mr-1" /> connected
              </BadgeTone>
            ) : (
              <BadgeTone tone="warn">demo mode</BadgeTone>
            )
          }
        />
        <div className="space-y-2">
          <div>
            <Label className="text-[11px] text-muted-foreground">Login (account)</Label>
            <Input value={login} onChange={(e) => setLogin(e.target.value)} className="h-8 text-xs" />
          </div>
          <div>
            <Label className="text-[11px] text-muted-foreground">Server</Label>
            <Input value={server} onChange={(e) => setServer(e.target.value)} className="h-8 text-xs" />
          </div>
          <div>
            <Label className="text-[11px] text-muted-foreground">Password</Label>
            <Input
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              type="password"
              placeholder="••••••••"
              className="h-8 text-xs"
            />
          </div>
          <div>
            <Label className="text-[11px] text-muted-foreground">Terminal path (Windows)</Label>
            <Input value={terminal} onChange={(e) => setTerminal(e.target.value)} className="h-8 text-xs font-mono" />
          </div>
          <SwitchRow
            label="Auto-launch MT5"
            desc="Start terminal64.exe automatically if not running"
            checked={autoLaunch}
            onChange={setAutoLaunch}
          />
          <div className="flex gap-2 pt-1">
            {mt5Connected ? (
              <Button variant="destructive" className="h-9 flex-1" onClick={disconnect}>
                <Unplug className="h-4 w-4 mr-1" /> Disconnect
              </Button>
            ) : (
              <Button className="h-9 flex-1" onClick={connect} disabled={connecting}>
                <Link2 className="h-4 w-4 mr-1" />
                {connecting ? "Connecting…" : "Connect & Launch MT5"}
              </Button>
            )}
          </div>
        </div>
      </Card>

      {/* Theme + broker */}
      <div className="space-y-3">
        <Card className="p-3">
          <SectionHeader title="Appearance" icon={theme === "dark" ? Moon : Sun} />
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => setTheme("dark")}
              className={cn(
                "rounded-lg border p-3 text-left transition-colors",
                theme === "dark" ? "border-primary bg-primary/5" : "border-border hover:bg-muted/40"
              )}
            >
              <Moon className="h-4 w-4 mb-1" />
              <div className="text-sm font-medium">Dark</div>
              <div className="text-[11px] text-muted-foreground">Trading terminal</div>
            </button>
            <button
              onClick={() => setTheme("light")}
              className={cn(
                "rounded-lg border p-3 text-left transition-colors",
                theme === "light" ? "border-primary bg-primary/5" : "border-border hover:bg-muted/40"
              )}
            >
              <Sun className="h-4 w-4 mb-1" />
              <div className="text-sm font-medium">Light</div>
              <div className="text-[11px] text-muted-foreground">Daytime reading</div>
            </button>
          </div>
        </Card>

        <Card className="p-3">
          <SectionHeader title="FINEX Account" icon={SettingsIcon} />
          <div className="grid grid-cols-2 gap-2">
            <StatTile label="Leverage" value={BROKER_SPEC.leverageFx} />
            <StatTile label="Spread" value={BROKER_SPEC.spreadFrom} />
            <StatTile label="Commission" value={BROKER_SPEC.commission} />
            <StatTile label="Min Volume" value={`${BROKER_SPEC.minVolume} lot`} />
            <StatTile label="Max Vol/Order" value={`${BROKER_SPEC.maxVolume}`} />
            <StatTile label="Max Positions" value={`${BROKER_SPEC.maxPositions}`} />
            <StatTile label="Margin Call" value={`${BROKER_SPEC.marginCall}%`} tone="warn" />
            <StatTile label="Stop Out" value={`${BROKER_SPEC.stopOut}%`} tone="down" />
          </div>
        </Card>
      </div>

      {/* AI Configuration */}
      <Card className="p-3">
        <SectionHeader
          title="AI Configuration"
          desc="Confidence thresholds + model per provider"
          icon={Cpu}
        />
        <div className="space-y-3">
          {/* Confidence sliders */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <Label className="text-[11px] text-muted-foreground">
                Manual Execute — Min Confidence
              </Label>
              <span className="text-xs font-semibold tnum">
                {store.aiMinConfidence}%
              </span>
            </div>
            <Slider
              value={[store.aiMinConfidence]}
              min={0} max={100} step={5}
              onValueChange={(v) => store.setAiMinConfidence(v[0])}
            />
            <p className="text-[10px] text-muted-foreground mt-0.5">
              Signals below this confidence are rejected when clicking Execute
            </p>
          </div>
          <Separator />
          <div>
            <div className="flex items-center justify-between mb-1">
              <Label className="text-[11px] text-muted-foreground">
                Auto-Trade — Min Confidence
              </Label>
              <span className="text-xs font-semibold tnum">
                {store.autoTradeMinConfidence}%
              </span>
            </div>
            <Slider
              value={[store.autoTradeMinConfidence]}
              min={50} max={100} step={5}
              onValueChange={(v) => store.setAutoTradeMinConfidence(v[0])}
            />
            <p className="text-[10px] text-muted-foreground mt-0.5">
              Auto-trade engine only executes signals at or above this confidence
            </p>
          </div>
          <Separator />
          {/* Model per provider — only Groq + Local (Ollama) supported */}
          <div className="text-[11px] text-muted-foreground font-medium">
            Model per Provider (configurable)
          </div>
          <div className="grid grid-cols-2 gap-2">
            {([
              { id: "groq", label: "Groq" },
              { id: "local", label: "Local (Ollama)" },
            ] as const).map((p) => (
              <div key={p.id}>
                <Label className="text-[10px] text-muted-foreground">{p.label} Model</Label>
                <Input
                  value={store.aiModels[p.id] ?? ""}
                  onChange={(e) => store.setAiModel(p.id, e.target.value)}
                  onBlur={() => {
                    // Auto-push model change to backend when user finishes typing
                    fetch("/api/trading/ai/config", {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({ models: store.aiModels }),
                    }).then(() => {
                      toast.success(`${p.label} model updated on backend: ${store.aiModels[p.id]}`);
                    }).catch(() => {});
                  }}
                  className="h-8 text-xs font-mono"
                  placeholder={`e.g. ${p.id === "groq" ? "llama-3.3-70b-versatile" : "llama3"}`}
                />
              </div>
            ))}
          </div>
          {/* Ollama context window + timeout — prevents OOM + timeout on local AI */}
          <div className="mt-3 p-2.5 rounded-md border border-border/60 bg-muted/20 space-y-2">
            <div>
              <Label className="text-[10px] text-muted-foreground">
                Ollama Context Window (tokens)
              </Label>
              <div className="flex items-center gap-2 mt-1">
                <Input
                  type="number"
                  min={1024}
                  max={131072}
                  step={1024}
                  value={store.ollamaNumCtx}
                  onChange={(e) => store.setOllamaNumCtx(parseInt(e.target.value) || 8192)}
                  onBlur={() => {
                    fetch("/api/trading/ai/config", {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({ ollama_num_ctx: store.ollamaNumCtx }),
                    }).then(() => {
                      toast.success(`Ollama context set to ${store.ollamaNumCtx} tokens`);
                    }).catch(() => {});
                  }}
                  className="h-8 text-xs font-mono w-28"
                />
                <span className="text-[10px] text-muted-foreground leading-tight">
                  Lower (4096) = less RAM, prevents OOM.<br />
                  Higher (16384) = more context, needs 32GB+ RAM.
                </span>
              </div>
            </div>
            <div>
              <Label className="text-[10px] text-muted-foreground">
                Ollama Timeout (seconds)
              </Label>
              <div className="flex items-center gap-2 mt-1">
                <Input
                  type="number"
                  min={30}
                  max={600}
                  step={10}
                  value={store.ollamaTimeout}
                  onChange={(e) => store.setOllamaTimeout(parseInt(e.target.value) || 120)}
                  onBlur={() => {
                    fetch("/api/trading/ai/config", {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({ ollama_timeout: store.ollamaTimeout }),
                    }).then(() => {
                      toast.success(`Ollama timeout set to ${store.ollamaTimeout}s`);
                    }).catch(() => {});
                  }}
                  className="h-8 text-xs font-mono w-28"
                />
                <span className="text-[10px] text-muted-foreground leading-tight">
                  Default 120s. Increase if timeout errors.<br />
                  Use smaller model (llama3) if still slow.
                </span>
              </div>
            </div>
          </div>
          <Button
            variant="default"
            size="sm"
            className="h-8 w-full mt-2"
            onClick={async () => {
              await pushAiConfig();
              toast.success("AI config applied to backend — models + confidence updated");
            }}
          >
            Apply to Backend (Runtime)
          </Button>
          <p className="text-[10px] text-muted-foreground mt-1">
            Click to push model + confidence changes to the Python backend instantly
            (no restart needed). Changes also persist in backend .env on next restart.
          </p>
        </div>
      </Card>

      {/* API keys */}
      <Card className="p-3">
        <SectionHeader
          title="API Keys & Integrations"
          desc="Stored locally only — never sent to server"
          icon={KeyRound}
        />
        <div className="space-y-2">
          <KeyField
            label="Finnhub API Key"
            value={keys.finnhub}
            onChange={(v) => setKey("finnhub", v)}
            placeholder="finnhub token"
          />
          <KeyField
            label="MARKETAUX API Key"
            value={keys.marketaux}
            onChange={(v) => setKey("marketaux", v)}
            placeholder="marketaux token"
          />
          <Separator />
          <KeyField
            label="Groq API Key"
            value={keys.groq}
            onChange={(v) => setKey("groq", v)}
            placeholder="groq token (free at console.groq.com)"
          />
        </div>
      </Card>

      {/* Python backend */}
      <Card className="p-3">
        <SectionHeader
          title="Python Backend"
          desc="FastAPI · MetaTrader 5 · ML pipeline"
          icon={Terminal}
          right={<BadgeTone tone={mt5Connected ? "up" : "warn"}>{mt5Connected ? "running" : "demo"}</BadgeTone>}
        />
        <div className="space-y-2 text-xs">
          <Row k="Runtime" v="Python 3.13+ · Windows 11" />
          <Row k="IDE" v="Visual Studio Code" />
          <Row k="Broker" v="FINEX Indonesia (real account)" />
          <Row k="MT5 Library" v="MetaTrader5 (pip)" />
          <Row k="ML Stack" v="scikit-learn · xgboost · pandas · ta" />
          <Row k="News APIs" v="Finnhub · MARKETAUX" />
          <Row k="AI Providers" v="Groq · Ollama (Local)" />
          <Separator />
          <div className="rounded-md bg-muted/40 p-2 font-mono text-[10px] leading-relaxed">
            <div className="text-muted-foreground"># start the backend on Windows</div>
            <div>cd python-backend</div>
            <div>pip install -r requirements.txt</div>
            <div>python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload</div>
          </div>
          <div className="text-[11px] text-muted-foreground">
            The dashboard auto-detects the backend. Without it, everything runs in
            simulation/demo mode with realistic synthetic data.
          </div>
        </div>
      </Card>
    </div>
  );
}

function KeyField({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
}) {
  return (
    <div>
      <Label className="text-[11px] text-muted-foreground">{label}</Label>
      <Input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        type="password"
        className="h-8 text-xs font-mono"
      />
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{k}</span>
      <span className="tnum">{v}</span>
    </div>
  );
}
