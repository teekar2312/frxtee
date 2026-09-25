"use client";

import * as React from "react";
import { Card } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import { Separator } from "@/components/ui/separator";
import { toast } from "sonner";
import {
  AlertTriangle,
  Crosshair,
  Gauge,
  ShieldCheck,
  Target,
  TrendingDown,
} from "lucide-react";
import { fmtMoney } from "@/lib/trading-data";
import { useTradingStore } from "@/lib/trading-store";
import {
  BadgeTone,
  ModeToggle,
  SectionHeader,
  StatTile,
  SwitchRow,
} from "./primitives";

function SliderRow({
  label,
  value,
  min,
  max,
  step,
  unit,
  onChange,
  hint,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  unit: string;
  onChange: (v: number) => void;
  hint?: string;
}) {
  return (
    <div className="py-1.5">
      <div className="flex items-center justify-between mb-1">
        <div>
          <div className="text-sm font-medium leading-tight">{label}</div>
          {hint ? (
            <div className="text-[11px] text-muted-foreground leading-tight">{hint}</div>
          ) : null}
        </div>
        <span className="text-sm font-semibold tnum">
          {value}
          <span className="text-muted-foreground ml-0.5 text-xs">{unit}</span>
        </span>
      </div>
      <Slider
        value={[value]}
        min={min}
        max={max}
        step={step}
        onValueChange={(v) => onChange(v[0])}
      />
      <div className="flex justify-between text-[9px] text-muted-foreground mt-0.5">
        <span>
          {min}
          {unit}
        </span>
        <span>
          {max}
          {unit}
        </span>
      </div>
    </div>
  );
}

export function RiskView() {
  const s = useTradingStore();
  const equity = s.accountEquity;

  const riskAmount = (equity * s.riskPerTrade) / 100;
  const dailyRiskAmt = (equity * s.dailyRiskLimit) / 100;
  const dailyTargetAmt = (equity * s.dailyTarget) / 100;

  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-3">
      <div className="space-y-3">
        <Card className="p-3">
          <SectionHeader
            title="Money Management"
            desc="Auto by AI or manual"
            icon={Gauge}
            right={
              <ModeToggle
                auto={s.autoRisk}
                onAuto={() => {
                  s.setAutoRisk(true);
                  s.setRiskPerTrade(0.8);
                  s.setStopLossPips(10);
                  s.setRrRatio(1.5);
                  s.setMaxOpenPositions(2);
                  s.setDailyRiskLimit(2.5);
                  s.setDailyTarget(2);
                  toast.success("AI optimized money management");
                }}
                onManual={() => s.setAutoRisk(false)}
              />
            }
          />
          <SliderRow
            label="Risk per Trade"
            value={s.riskPerTrade}
            min={0.5}
            max={1}
            step={0.1}
            unit="%"
            onChange={s.setRiskPerTrade}
            hint={`${fmtMoney(riskAmount)} per position`}
          />
          <Separator />
          <SliderRow
            label="Stop Loss"
            value={s.stopLossPips}
            min={5}
            max={15}
            step={1}
            unit="p"
            onChange={s.setStopLossPips}
            hint="5–15 pips (scalping)"
          />
          <Separator />
          <SliderRow
            label="Risk : Reward"
            value={s.rrRatio}
            min={1}
            max={3}
            step={0.1}
            unit=":1"
            onChange={s.setRrRatio}
            hint={`TP = ${s.stopLossPips * s.rrRatio} pips`}
          />
          <Separator />
          <SliderRow
            label="Max Open Positions"
            value={s.maxOpenPositions}
            min={1}
            max={3}
            step={1}
            unit=""
            onChange={s.setMaxOpenPositions}
            hint="1–3 concurrent (anti-MC)"
          />
        </Card>

        <Card className="p-3">
          <SectionHeader title="Daily Risk (Anti-MC)" icon={ShieldCheck} />
          <SliderRow
            label="Daily Risk Limit"
            value={s.dailyRiskLimit}
            min={2}
            max={3}
            step={0.1}
            unit="%"
            onChange={s.setDailyRiskLimit}
            hint={`${fmtMoney(dailyRiskAmt)} — halt new trades if exceeded`}
          />
          <SliderRow
            label="Daily Target"
            value={s.dailyTarget}
            min={1}
            max={3}
            step={0.1}
            unit="%"
            onChange={s.setDailyTarget}
            hint={`${fmtMoney(dailyTargetAmt)} realistic daily goal`}
          />
          <SwitchRow
            label="Avoid high-impact news"
            desc="Halt scalping entries near tier-1 events"
            checked={s.avoidNews}
            onChange={s.setAvoidNews}
          />
        </Card>
      </div>

      <div className="space-y-3">
        <Card className="p-3">
          <SectionHeader
            title="Trailing Stop"
            desc="Lock profit as price moves favorably"
            icon={Crosshair}
            right={
              <ModeToggle
                auto={s.autoTrailing}
                onAuto={() => {
                  s.setAutoTrailing(true);
                  s.setTrailingPips(8);
                  toast.success("AI configured trailing stop");
                }}
                onManual={() => s.setAutoTrailing(false)}
              />
            }
          />
          <SwitchRow
            label="Enable trailing stop"
            desc="Applies to new & open positions"
            checked={s.trailingEnabled}
            onChange={s.setTrailingEnabled}
          />
          <Separator />
          <SliderRow
            label="Trail Distance"
            value={s.trailingPips}
            min={3}
            max={20}
            step={1}
            unit="p"
            onChange={s.setTrailingPips}
            hint="Distance behind current price"
          />
          <div className="grid grid-cols-2 gap-2 mt-2">
            <div className="rounded-md border bg-muted/30 p-2">
              <div className="text-[10px] text-muted-foreground">Activation</div>
              <div className="text-xs font-medium">After +{s.trailingPips}p profit</div>
            </div>
            <div className="rounded-md border bg-muted/30 p-2">
              <div className="text-[10px] text-muted-foreground">Step</div>
              <div className="text-xs font-medium">Every +1 pip move</div>
            </div>
          </div>
        </Card>

        <Card className="p-3">
          <SectionHeader title="Position Sizing Calculator" icon={Target} />
          <div className="space-y-2 text-xs">
            <Row k="Account Equity" v={fmtMoney(equity)} />
            <Row k="Risk per Trade" v={`${s.riskPerTrade}% (${fmtMoney(riskAmount)})`} />
            <Row k="Stop Loss" v={`${s.stopLossPips} pips`} />
            <Row k="Value per pip (1 lot)" v="$10 / pip" />
            <Separator />
            <Row
              k="Suggested Lot Size"
              v={`${(riskAmount / (s.stopLossPips * 10)).toFixed(2)} lot`}
              tone
            />
            <Row k="Take Profit" v={`${(s.stopLossPips * s.rrRatio).toFixed(1)} pips`} tone />
            <Row
              k="Potential Loss"
              v={fmtMoney(-riskAmount)}
              tone="down"
            />
            <Row
              k="Potential Profit"
              v={fmtMoney(riskAmount * s.rrRatio)}
              tone="up"
            />
          </div>
        </Card>
      </div>

      <div className="space-y-3">
        <Card className="p-3">
          <SectionHeader title="Risk Dashboard" icon={TrendingDown} />
          <div className="grid grid-cols-2 gap-2">
            <StatTile label="Today Risk Used" value="0.8%" sub="of 3.0% limit" tone="up" />
            <StatTile label="Margin Level" value="1,840%" sub="healthy" tone="up" />
            <StatTile label="Free Margin" value={fmtMoney(equity * 0.94)} />
            <StatTile label="Max DD (30d)" value="-4.2%" tone="down" />
          </div>
        </Card>

        <Card className="p-3">
          <SectionHeader title="FINEX Account Limits" icon={AlertTriangle} />
          <div className="space-y-1.5 text-xs">
            <Row k="Leverage (FX & Metals)" v="1 : 500" />
            <Row k="Spread" v="from 0.5 pip (floating)" />
            <Row k="Commission" v="$1 / lot / side" />
            <Row k="Min Volume" v="0.01 lot" />
            <Row k="Max Volume / Order" v="50 lot" />
            <Row k="Max Open Positions" v="200" />
            <Row k="Margin Call" v="50%" tone="warn" />
            <Row k="Stop Out" v="20%" tone="down" />
          </div>
        </Card>

        <Card className="p-3">
          <SectionHeader title="Active Rules" icon={ShieldCheck} />
          <div className="space-y-1.5">
            {[
              ["Risk ≤ 1% / trade", true],
              ["Daily risk ≤ 3%", true],
              ["Max 3 concurrent", true],
              ["Avoid high-impact news", s.avoidNews],
              ["Trailing stop ON", s.trailingEnabled],
              ["RR ≥ 1:1.5", s.rrRatio >= 1.5],
            ].map(([label, ok]) => (
              <div key={label as string} className="flex items-center justify-between text-xs">
                <span>{label as string}</span>
                <BadgeTone tone={ok ? "up" : "warn"}>{ok ? "enforced" : "off"}</BadgeTone>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

function Row({
  k,
  v,
  tone,
}: {
  k: string;
  v: string;
  tone?: boolean | "up" | "down";
}) {
  const toneCls =
    tone === "up"
      ? "text-success"
      : tone === "down"
      ? "text-danger"
      : tone === true
      ? "text-primary font-semibold"
      : "text-foreground";
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{k}</span>
      <span className={`tnum ${toneCls}`}>{v}</span>
    </div>
  );
}
