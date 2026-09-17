"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Sparkles, Hand } from "lucide-react";

/** Compact stat tile */
export function StatTile({
  label,
  value,
  sub,
  tone = "default",
  className,
}: {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  tone?: "default" | "up" | "down" | "warn";
  className?: string;
}) {
  const toneCls =
    tone === "up"
      ? "text-success"
      : tone === "down"
      ? "text-danger"
      : tone === "warn"
      ? "text-warning"
      : "text-foreground";
  return (
    <Card className={cn("p-3 gap-0.5", className)}>
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className={cn("text-lg font-semibold tnum leading-tight", toneCls)}>
        {value}
      </div>
      {sub ? (
        <div className="text-[11px] text-muted-foreground tnum">{sub}</div>
      ) : null}
    </Card>
  );
}

/** Auto/Manual mode toggle pill */
export function ModeToggle({
  auto,
  onAuto,
  onManual,
  size = "sm",
}: {
  auto: boolean;
  onAuto: () => void;
  onManual: () => void;
  size?: "sm" | "md";
}) {
  const h = size === "sm" ? "h-7" : "h-8";
  return (
    <div
      className={cn(
        "inline-flex items-center rounded-md border bg-muted/50 p-0.5 text-xs font-medium",
        h
      )}
    >
      <button
        type="button"
        onClick={onAuto}
        className={cn(
          "inline-flex items-center gap-1 rounded px-2 py-0.5 transition-colors",
          auto
            ? "bg-primary text-primary-foreground"
            : "text-muted-foreground hover:text-foreground"
        )}
      >
        <Sparkles className="h-3 w-3" /> AI
      </button>
      <button
        type="button"
        onClick={onManual}
        className={cn(
          "inline-flex items-center gap-1 rounded px-2 py-0.5 transition-colors",
          !auto
            ? "bg-primary text-primary-foreground"
            : "text-muted-foreground hover:text-foreground"
        )}
      >
        <Hand className="h-3 w-3" /> Manual
      </button>
    </div>
  );
}

/** A labelled auto/manual row */
export function AutoManualRow({
  label,
  desc,
  auto,
  onAuto,
  onManual,
  right,
}: {
  label: string;
  desc?: string;
  auto: boolean;
  onAuto: () => void;
  onManual: () => void;
  right?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-2 py-1.5">
      <div className="min-w-0">
        <div className="text-sm font-medium leading-tight">{label}</div>
        {desc ? (
          <div className="text-[11px] text-muted-foreground leading-tight">
            {desc}
          </div>
        ) : null}
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {right}
        <ModeToggle auto={auto} onAuto={onAuto} onManual={onManual} />
      </div>
    </div>
  );
}

/** Chip toggle (multi-select) */
export function Chip({
  active,
  onClick,
  children,
  className,
  title,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  className?: string;
  title?: string;
}) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs font-medium transition-colors",
        active
          ? "border-primary bg-primary text-primary-foreground"
          : "border-border bg-card text-muted-foreground hover:text-foreground hover:border-foreground/30",
        className
      )}
    >
      {children}
    </button>
  );
}

/** Compact section header */
export function SectionHeader({
  title,
  desc,
  right,
  icon: Icon,
}: {
  title: string;
  desc?: string;
  right?: React.ReactNode;
  icon?: React.ComponentType<{ className?: string }>;
}) {
  return (
    <div className="flex items-center justify-between gap-2 mb-2">
      <div className="flex items-center gap-2 min-w-0">
        {Icon ? <Icon className="h-4 w-4 text-muted-foreground shrink-0" /> : null}
        <div className="min-w-0">
          <h2 className="text-sm font-semibold leading-tight truncate">{title}</h2>
          {desc ? (
            <p className="text-[11px] text-muted-foreground leading-tight truncate">
              {desc}
            </p>
          ) : null}
        </div>
      </div>
      {right ? <div className="shrink-0">{right}</div> : null}
    </div>
  );
}

/** Small labelled switch row */
export function SwitchRow({
  label,
  desc,
  checked,
  onChange,
}: {
  label: string;
  desc?: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-2 py-1.5">
      <div className="min-w-0">
        <div className="text-sm font-medium leading-tight">{label}</div>
        {desc ? (
          <div className="text-[11px] text-muted-foreground leading-tight">
            {desc}
          </div>
        ) : null}
      </div>
      <Switch checked={checked} onCheckedChange={onChange} />
    </div>
  );
}

export function BadgeTone({
  children,
  tone,
}: {
  children: React.ReactNode;
  tone: "up" | "down" | "neutral" | "warn";
}) {
  const cls =
    tone === "up"
      ? "bg-success/15 text-success border-success/30"
      : tone === "down"
      ? "bg-danger/15 text-danger border-danger/30"
      : tone === "warn"
      ? "bg-warning/15 text-warning border-warning/30"
      : "bg-muted text-muted-foreground border-border";
  return (
    <span
      className={cn(
        "inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] font-medium",
        cls
      )}
    >
      {children}
    </span>
  );
}
