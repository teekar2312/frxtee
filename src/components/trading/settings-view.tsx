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
  const { mt5Connected, setMt5Connected, demoMode, toggleDemo, keys, setKey } = store;
  const [login, setLogin] = React.useState("5012****");
  const [server, setServer] = React.useState("FINEX-Real");
  const [password, setPassword] = React.useState("");
  const [terminal, setTerminal] = React.useState(
    "C:\\Program Files\\FINEX MetaTrader 5\\terminal64.exe"
  );
  const [connecting, setConnecting] = React.useState(false);
  const [autoLaunch, setAutoLaunch] = React.useState(true);

  async function connect() {
    setConnecting(true);
    try {
      const r = await fetch("/api/trading/connect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ login, server, autoLaunch, terminal }),
      });
      const d = await r.json();
      if (d.connected) {
        setMt5Connected(true);
        useTradingStore.setState({ demoMode: false });
        toast.success(d.message);
      }
    } catch {
      toast.error("Connection failed");
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
          {/* Model per provider */}
          <div className="text-[11px] text-muted-foreground font-medium">
            Model per Provider (configurable)
          </div>
          <div className="grid grid-cols-2 gap-2">
            {([
              { id: "zai", label: "Z.AI" },
              { id: "groq", label: "Groq" },
              { id: "google", label: "Google AI" },
              { id: "local", label: "Local (Ollama)" },
            ] as const).map((p) => (
              <div key={p.id}>
                <Label className="text-[10px] text-muted-foreground">{p.label} Model</Label>
                <Input
                  value={store.aiModels[p.id] ?? ""}
                  onChange={(e) => store.setAiModel(p.id, e.target.value)}
                  className="h-8 text-xs font-mono"
                  placeholder={`e.g. ${p.id === "zai" ? "glm-4.6" : p.id === "groq" ? "llama-3.3-70b" : p.id === "google" ? "gemini-1.5-pro" : "llama3"}`}
                />
              </div>
            ))}
          </div>
          <p className="text-[10px] text-muted-foreground">
            These models are sent to the Python backend via .env (ZAI_MODEL,
            GROQ_MODEL, GOOGLE_MODEL, OLLAMA_MODEL). Update backend .env to match.
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
            label="Z.AI API Key"
            value={keys.zai}
            onChange={(v) => setKey("zai", v)}
            placeholder="z.ai token"
          />
          <KeyField
            label="Groq API Key"
            value={keys.groq}
            onChange={(v) => setKey("groq", v)}
            placeholder="groq token"
          />
          <KeyField
            label="Google AI Studio Key"
            value={keys.google}
            onChange={(v) => setKey("google", v)}
            placeholder="google token"
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
          <Row k="Runtime" v="Python 3.14 · Windows 11" />
          <Row k="IDE" v="Visual Studio Code" />
          <Row k="Broker" v="FINEX Indonesia (real account)" />
          <Row k="MT5 Library" v="MetaTrader5 (pip)" />
          <Row k="ML Stack" v="scikit-learn · xgboost · pandas · ta" />
          <Row k="News APIs" v="Finnhub · MARKETAUX" />
          <Row k="AI Providers" v="Z.AI · Groq · Google · Ollama" />
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
