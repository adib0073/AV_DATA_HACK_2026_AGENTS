"use client";

import { Check, Eye, Loader2 } from "lucide-react";
import type { ActivityItem } from "@/lib/types";
import { NODE_ACCENT, NODE_ICON } from "./icons";

export interface Stage {
  key: string;
  label: string;
  status: "pending" | "active" | "done" | "skipped";
}

export default function AgentActivity({
  stages,
  log,
  running,
}: {
  stages: Stage[];
  log: ActivityItem[];
  running: boolean;
}) {
  return (
    <div className="glass p-5">
      <div className="flex items-center gap-2 mb-4">
        <Eye className="h-4 w-4 text-brand-600" />
        <h2 className="text-sm font-bold tracking-wide text-ink">
          Agent activity
        </h2>
        {running && (
          <span className="ml-auto inline-flex items-center gap-1.5 text-[11px] font-semibold text-brand-600">
            <span className="h-1.5 w-1.5 rounded-full bg-brand-500 animate-pulse" />
            live
          </span>
        )}
      </div>

      {/* Pipeline strip */}
      <div className="flex flex-wrap gap-1.5 mb-5">
        {stages.map((s) => {
          const Icon = NODE_ICON[s.key] ?? Check;
          const base =
            "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium border transition-colors";
          const cls =
            s.status === "done"
              ? "border-emerald-200 bg-emerald-50 text-emerald-700"
              : s.status === "active"
                ? "border-brand-300 bg-brand-50 text-brand-700"
                : s.status === "skipped"
                  ? "border-slate-200 bg-slate-50 text-slate-400"
                  : "border-slate-200 bg-white text-slate-500";
          return (
            <span key={s.key} className={`${base} ${cls}`}>
              {s.status === "active" ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : s.status === "done" ? (
                <Check className="h-3 w-3" />
              ) : (
                <Icon className="h-3 w-3" />
              )}
              {s.label}
            </span>
          );
        })}
      </div>

      {/* Live timeline */}
      <div className="space-y-2.5 max-h-[42vh] overflow-y-auto pr-1">
        {log.length === 0 && !running && (
          <p className="text-xs text-slate-400">
            The agents&apos; steps will appear here as they work.
          </p>
        )}
        {log.map((item) => {
          const Icon = NODE_ICON[item.node] ?? Check;
          const accent = NODE_ACCENT[item.node] ?? "text-slate-500";
          return (
            <div
              key={item.id}
              className="flex items-start gap-3 animate-fade-up"
            >
              <div className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg border border-slate-200 bg-slate-50">
                <Icon className={`h-3.5 w-3.5 ${accent}`} />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-slate-800">
                    {item.label}
                  </span>
                  <Check className="h-3 w-3 text-emerald-500" />
                </div>
                {item.detail && (
                  <p className="text-xs text-slate-500 truncate">{item.detail}</p>
                )}
              </div>
            </div>
          );
        })}
        {running && (
          <div className="flex items-center gap-3 text-slate-500">
            <div className="grid h-7 w-7 shrink-0 place-items-center rounded-lg border border-slate-200 bg-slate-50">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-brand-600" />
            </div>
            <span className="text-sm">Working…</span>
          </div>
        )}
      </div>
    </div>
  );
}
