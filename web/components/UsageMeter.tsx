"use client";

import { Coins, Cpu, Gauge } from "lucide-react";
import type { AppConfig, Usage } from "@/lib/types";

export default function UsageMeter({
  usage,
  config,
}: {
  usage: Usage;
  config: AppConfig | null;
}) {
  return (
    <div className="glass p-5">
      <div className="flex items-center gap-2 mb-4">
        <Gauge className="h-4 w-4 text-teal-500" />
        <h2 className="text-sm font-semibold tracking-wide text-slate-200">
          Tokens &amp; cost
        </h2>
        <span className="ml-auto text-[11px] text-slate-500">this session</span>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Stat label="LLM calls" value={usage.calls.toString()} />
        <Stat
          label="Est. cost"
          value={`$${usage.cost_usd.toFixed(4)}`}
          highlight
        />
        <Stat label="Input tok" value={usage.input_tokens.toLocaleString()} />
        <Stat label="Output tok" value={usage.output_tokens.toLocaleString()} />
      </div>

      {config && (
        <div className="mt-4 flex flex-wrap gap-1.5">
          <Badge icon={<Cpu className="h-3 w-3" />}>{config.model}</Badge>
          <Badge>{config.use_gateway ? "MCP via Obot" : "MCP direct"}</Badge>
          <Badge icon={<Coins className="h-3 w-3" />}>
            {config.ai_gateway ? "AI gateway on" : "OpenAI direct"}
          </Badge>
          {config.inject_regression && (
            <Badge tone="warn">regression ON</Badge>
          )}
        </div>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2.5">
      <div className="text-[11px] uppercase tracking-wide text-slate-500">
        {label}
      </div>
      <div
        className={`mt-0.5 text-lg font-semibold tabular-nums ${
          highlight ? "gradient-text" : "text-slate-100"
        }`}
      >
        {value}
      </div>
    </div>
  );
}

function Badge({
  children,
  icon,
  tone = "default",
}: {
  children: React.ReactNode;
  icon?: React.ReactNode;
  tone?: "default" | "warn";
}) {
  const cls =
    tone === "warn"
      ? "border-amber-400/30 bg-amber-400/10 text-amber-200"
      : "border-white/10 bg-white/[0.03] text-slate-300";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] ${cls}`}
    >
      {icon}
      {children}
    </span>
  );
}
