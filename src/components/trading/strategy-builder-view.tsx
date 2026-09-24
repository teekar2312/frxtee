"use client";

import * as React from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { Plus, Trash2, Play, GitBranch } from "lucide-react";
import { cn } from "@/lib/utils";
import { TECHNICAL_INDICATORS } from "@/lib/trading-data";
import { BadgeTone, SectionHeader, Chip } from "./primitives";

interface Rule {
  id: string;
  indicator: string;
  operator: string;
  value: string;
}

const OPERATORS = [">", "<", ">=", "<=", "==", "crosses_up", "crosses_down"];

export function StrategyBuilderView() {
  const [rules, setRules] = React.useState<Rule[]>([
    { id: "1", indicator: "rsi", operator: "<", value: "30" },
    { id: "2", indicator: "ema", operator: "crosses_up", value: "20" },
  ]);
  const [name, setName] = React.useState("My Scalping Strategy");

  function addRule() {
    setRules((r) => [...r, {
      id: Date.now().toString(),
      indicator: "rsi",
      operator: ">",
      value: "50",
    }]);
  }

  function removeRule(id: string) {
    setRules((r) => r.filter((x) => x.id !== id));
  }

  function updateRule(id: string, field: keyof Rule, value: string) {
    setRules((r) => r.map((x) => x.id === id ? { ...x, [field]: value } : x));
  }

  const strategyJson = React.useMemo(() => JSON.stringify({
    name,
    rules: rules.map(({ indicator, operator, value }) => ({
      indicator, operator, value: parseFloat(value) || 0,
    })),
  }, null, 2), [name, rules]);

  return (
    <div className="space-y-3">
      <Card className="p-3">
        <SectionHeader
          title="Strategy Builder"
          desc="Build custom strategies with visual rules — no coding needed"
          icon={GitBranch}
          right={
            <Button size="sm" className="h-7 text-xs" onClick={() =>
              toast.success("Strategy saved", { description: `${name} with ${rules.length} rules` })
            }>
              Save Strategy
            </Button>
          }
        />
        <div className="mb-3">
          <label className="text-[11px] text-muted-foreground">Strategy Name</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full h-8 px-2 text-sm rounded-md border bg-transparent mt-1"
          />
        </div>
        <div className="space-y-2">
          {rules.map((rule, i) => (
            <div key={rule.id} className="flex items-center gap-2">
              <Badge variant="secondary" className="text-[10px] shrink-0">{i + 1}</Badge>
              <Select value={rule.indicator} onValueChange={(v) => updateRule(rule.id, "indicator", v)}>
                <SelectTrigger className="h-8 w-32 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {TECHNICAL_INDICATORS.map((ind) => (
                    <SelectItem key={ind.id} value={ind.id} className="text-xs">
                      {ind.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={rule.operator} onValueChange={(v) => updateRule(rule.id, "operator", v)}>
                <SelectTrigger className="h-8 w-28 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {OPERATORS.map((op) => (
                    <SelectItem key={op} value={op} className="text-xs">{op}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <input
                value={rule.value}
                onChange={(e) => updateRule(rule.id, "value", e.target.value)}
                type="number"
                className="h-8 w-20 px-2 text-sm rounded-md border bg-transparent"
              />
              <Button
                variant="ghost" size="sm"
                className="h-8 text-danger shrink-0"
                onClick={() => removeRule(rule.id)}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          ))}
        </div>
        <Button variant="outline" size="sm" className="h-8 mt-2 w-full" onClick={addRule}>
          <Plus className="h-3.5 w-3.5 mr-1" /> Add Rule
        </Button>
      </Card>

      <Card className="p-3">
        <SectionHeader title="Strategy JSON Preview" icon={Play} />
        <pre className="text-[11px] font-mono bg-muted/30 rounded-md p-3 overflow-x-auto scroll-thin max-h-48">
          {strategyJson}
        </pre>
        <div className="flex items-center gap-2 mt-2">
          <Button
            variant="outline" size="sm" className="h-7 text-xs"
            onClick={() => toast.info("Backtest with this strategy…")}
          >
            <Play className="h-3 w-3 mr-1" /> Backtest
          </Button>
          <Button
            variant="outline" size="sm" className="h-7 text-xs"
            onClick={() => toast.info("Deploy to auto-trade…")}
          >
            Deploy
          </Button>
        </div>
      </Card>
    </div>
  );
}
