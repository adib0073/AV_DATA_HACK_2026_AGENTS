"use client";

import { type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  CheckCircle2,
  Clock,
  Coins,
  Database,
  ExternalLink,
  FlaskConical,
  Gauge,
  Layers,
  Loader2,
  Network,
  Play,
  RotateCcw,
  Server,
  Upload,
  Wrench,
} from "lucide-react";

import FlowDiagram from "@/components/FlowDiagram";
import {
  captureFlow,
  getEvalConfig,
  getFlowTopology,
  getGoldens,
  getObservability,
  parseGoldensFile,
  resetGoldens,
  runEval,
  uploadGoldens,
} from "@/lib/evals";
import type {
  EvalConfig,
  EvalResult,
  EvalTable,
  FlowResponse,
  GoldenItem,
  Observability,
} from "@/lib/types";

export default function EvalStudio() {
  const [config, setConfig] = useState<EvalConfig | null>(null);
  const [goldens, setGoldens] = useState<GoldenItem[]>([]);
  const [custom, setCustom] = useState(false);
  const [obs, setObs] = useState<Observability | null>(null);

  const [suite, setSuite] = useState("layer1");
  const [limit, setLimit] = useState<string>("5");
  const [regression, setRegression] = useState<"on" | "off">("on");

  const [running, setRunning] = useState(false);
  const [log, setLog] = useState<string[]>([]);
  const [result, setResult] = useState<EvalResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const logRef = useRef<HTMLPreElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const activeSuite = useMemo(
    () => config?.suites.find((s) => s.id === suite),
    [config, suite],
  );

  useEffect(() => {
    refreshConfig();
    refreshGoldens();
    refreshObs();
  }, []);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [log]);

  async function refreshConfig() {
    try {
      setConfig(await getEvalConfig());
    } catch {
      /* api may be warming up */
    }
  }
  async function refreshGoldens() {
    try {
      const g = await getGoldens();
      setGoldens(g.goldens);
      setCustom(g.custom);
    } catch {
      /* ignore */
    }
  }
  async function refreshObs() {
    try {
      setObs(await getObservability());
    } catch {
      /* ignore */
    }
  }

  async function onRun() {
    if (running) return;
    setRunning(true);
    setLog([]);
    setResult(null);
    setError(null);
    const parsedLimit = limit.trim() ? Number(limit) : null;
    await runEval(
      {
        suite,
        limit: Number.isFinite(parsedLimit as number) ? parsedLimit : null,
        regression: activeSuite?.supports_regression ? regression : null,
      },
      {
        onLog: (line) => setLog((l) => [...l, line]),
        onResult: (r) => setResult(r),
        onError: (m) => setError(m),
        onDone: () => {
          setRunning(false);
          refreshObs();
          refreshConfig();
        },
      },
    );
    setRunning(false);
  }

  async function onUpload(file: File) {
    setNotice(null);
    setError(null);
    try {
      const text = await file.text();
      const items = parseGoldensFile(file.name, text);
      if (!items.length) throw new Error("No valid goldens found in the file.");
      const res = await uploadGoldens(items);
      setNotice(`Loaded ${res.count} custom goldens.`);
      refreshGoldens();
      refreshConfig();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed.");
    } finally {
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function onResetGoldens() {
    try {
      const res = await resetGoldens();
      setNotice(`Reverted to the built-in ${res.count} goldens.`);
      refreshGoldens();
      refreshConfig();
    } catch {
      setError("Could not reset goldens.");
    }
  }

  return (
    <div className="mx-auto grid max-w-7xl gap-5 px-4 pb-12 lg:grid-cols-[1fr_380px]">
      {/* Main column */}
      <div className="space-y-5">
        {/* Run controls */}
        <section className="glass p-5">
          <div className="mb-4 flex items-center gap-2">
            <FlaskConical className="h-4 w-4 text-brand-300" />
            <h2 className="text-sm font-semibold text-slate-100">Run the eval suite</h2>
            {config && (
              <span className="ml-auto text-[11px] text-slate-400">
                agent <b className="text-slate-200">{config.model}</b> · judge{" "}
                <b className="text-slate-200">{config.judge_model}</b>
                {config.use_gateway && " · gateway ON"}
              </span>
            )}
          </div>

          <div className="grid gap-2 sm:grid-cols-3">
            {config?.suites.map((s) => (
              <button
                key={s.id}
                onClick={() => setSuite(s.id)}
                className={`rounded-xl border p-3 text-left transition ${
                  suite === s.id
                    ? "border-brand-400/60 bg-brand-500/10"
                    : "border-white/10 bg-white/[0.02] hover:bg-white/[0.05]"
                }`}
              >
                <div className="flex items-center gap-1.5 text-sm font-medium text-slate-100">
                  {s.name}
                  {!s.judged && (
                    <span className="rounded bg-teal-500/15 px-1.5 py-0.5 text-[10px] text-teal-300">
                      fast
                    </span>
                  )}
                </div>
              </button>
            ))}
          </div>

          {activeSuite && (
            <p className="mt-3 text-xs leading-relaxed text-slate-400">{activeSuite.desc}</p>
          )}

          <div className="mt-4 flex flex-wrap items-end gap-4">
            <label className="text-xs text-slate-300">
              <span className="mb-1 block text-slate-400">Limit (goldens)</span>
              <input
                value={limit}
                onChange={(e) => setLimit(e.target.value.replace(/[^0-9]/g, ""))}
                placeholder="all"
                className="w-24 rounded-lg border border-white/10 bg-white/[0.03] px-2.5 py-1.5 text-slate-100 focus:border-brand-400/50 focus:outline-none"
              />
            </label>

            {activeSuite?.supports_regression && (
              <label className="text-xs text-slate-300">
                <span className="mb-1 block text-slate-400">Seeded regression</span>
                <div className="flex overflow-hidden rounded-lg border border-white/10">
                  {(["on", "off"] as const).map((v) => (
                    <button
                      key={v}
                      onClick={() => setRegression(v)}
                      className={`px-3 py-1.5 transition ${
                        regression === v
                          ? v === "on"
                            ? "bg-rose-500/80 text-white"
                            : "bg-emerald-500/80 text-white"
                          : "bg-white/[0.03] text-slate-300 hover:bg-white/[0.06]"
                      }`}
                    >
                      {v}
                    </button>
                  ))}
                </div>
              </label>
            )}

            <button
              onClick={onRun}
              disabled={running}
              className="ml-auto flex items-center gap-2 rounded-xl bg-brand-500 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {running ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              {running ? "Running…" : "Run eval"}
            </button>
          </div>

          {error && (
            <div className="mt-3 rounded-lg border border-rose-400/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
              {error}
            </div>
          )}
        </section>

        {/* Flow & traces (Layer 3 + Layer 4 in one view) */}
        <FlowPanel />

        {/* Results */}
        {result && <ResultView result={result} />}

        {/* Live console */}
        {(running || log.length > 0) && (
          <section className="glass p-5">
            <div className="mb-2 flex items-center gap-2">
              <Activity className="h-4 w-4 text-slate-400" />
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                Live console
              </h3>
            </div>
            <pre
              ref={logRef}
              className="max-h-72 overflow-auto whitespace-pre rounded-lg border border-white/10 bg-black/40 p-3 text-[11px] leading-relaxed text-slate-300"
            >
              {log.join("\n") || "Starting…"}
            </pre>
          </section>
        )}

        {/* Observability dashboard (Confident AI + Obot, in one view) */}
        <ObservabilityDashboard obs={obs} />
      </div>

      {/* Right rail */}
      <aside className="space-y-5">
        <GoldensCard
          goldens={goldens}
          custom={custom}
          notice={notice}
          onUploadClick={() => fileRef.current?.click()}
          onReset={onResetGoldens}
        />
        <input
          ref={fileRef}
          type="file"
          accept=".json,.csv"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onUpload(f);
          }}
        />
        <RecentRunsCard obs={obs} />
      </aside>
    </div>
  );
}

/* -------------------------------------------------------------------------- */

function statusColor(v: string): string {
  const u = v.toUpperCase();
  if (["PASS", "FIXED", "OK"].includes(u)) return "text-emerald-300";
  if (["FAIL", "BROKEN", "REGRESSED"].includes(u)) return "text-rose-300";
  return "text-slate-300";
}

function FlowPanel() {
  const [flow, setFlow] = useState<FlowResponse | null>(null);
  const [capturing, setCapturing] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    getFlowTopology()
      .then(setFlow)
      .catch(() => setErr("Could not load the flow topology."));
  }, []);

  async function onCapture() {
    if (capturing) return;
    setCapturing(true);
    setErr(null);
    try {
      setFlow(await captureFlow());
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Capture failed.");
    } finally {
      setCapturing(false);
    }
  }

  return (
    <section className="glass p-5">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Network className="h-4 w-4 text-brand-300" />
        <h2 className="text-sm font-semibold text-slate-100">Call flow &amp; traces</h2>
        <span className="rounded bg-indigo-500/15 px-1.5 py-0.5 text-[10px] text-indigo-200">
          Layer 3 · spans
        </span>
        <span className="rounded bg-teal-500/15 px-1.5 py-0.5 text-[10px] text-teal-200">
          Layer 4 · gateway
        </span>
        <button
          onClick={onCapture}
          disabled={capturing}
          className="ml-auto flex items-center gap-2 rounded-xl border border-brand-400/40 bg-brand-500/10 px-4 py-2 text-xs font-semibold text-brand-100 transition hover:bg-brand-500/20 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {capturing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
          {capturing ? "Running one trip…" : "Capture live trace"}
        </button>
      </div>

      <p className="mb-3 text-xs leading-relaxed text-slate-400">
        Orchestrator → specialist agents → {flow?.use_gateway ? "Obot MCP gateway → " : ""}
        MCP servers → tools.{" "}
        {flow?.ran
          ? "Highlighted nodes fired in the captured run."
          : "Run a trip to highlight the path it actually took."}
      </p>

      {err && (
        <div className="mb-3 rounded-lg border border-rose-400/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
          {err}
        </div>
      )}

      {flow?.graph && <FlowDiagram graph={flow.graph} />}

      <div className="mt-3 flex flex-wrap items-center gap-3 text-[11px]">
        <LegendDot className="bg-emerald-400" label="fired in this run" />
        {flow?.confident_observatory && (
          <a
            href={flow.confident_observatory}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1 text-brand-300 hover:text-brand-200"
          >
            Layer 3 · trace timeline (Confident AI)
            <ExternalLink className="h-3 w-3" />
          </a>
        )}
        {flow?.obot_url && (
          <a
            href={flow.obot_url}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1 text-teal-300 hover:text-teal-200"
          >
            Layer 4 · gateway audit (Obot)
            <ExternalLink className="h-3 w-3" />
          </a>
        )}
        {flow?.usage && (
          <span className="ml-auto flex items-center gap-1 text-slate-400">
            <Gauge className="h-3.5 w-3.5" />
            {flow.usage.calls} calls · {flow.usage.total_tokens.toLocaleString()} tok · $
            {flow.usage.cost_usd.toFixed(4)}
          </span>
        )}
      </div>

      {flow?.calls && flow.calls.length > 0 && (
        <div className="mt-4">
          <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
            Tool calls this run ({flow.calls.length})
          </div>
          <div className="overflow-x-auto rounded-lg border border-white/10">
            <table className="w-full text-left text-[11px]">
              <thead className="bg-white/[0.04] text-slate-400">
                <tr>
                  <th className="px-3 py-2 font-medium">#</th>
                  <th className="px-3 py-2 font-medium">Agent</th>
                  <th className="px-3 py-2 font-medium">MCP server</th>
                  <th className="px-3 py-2 font-medium">Tool</th>
                  <th className="px-3 py-2 font-medium">Args</th>
                </tr>
              </thead>
              <tbody>
                {flow.calls.map((c, i) => (
                  <tr key={i} className="border-t border-white/5">
                    <td className="px-3 py-2 text-slate-500">{i + 1}</td>
                    <td className="px-3 py-2 text-slate-200">{c.agent}</td>
                    <td className="px-3 py-2 text-slate-300">{c.server}</td>
                    <td className="px-3 py-2 font-mono text-brand-200">{c.tool}</td>
                    <td className="px-3 py-2 font-mono text-slate-400">
                      {Object.keys(c.args || {}).length
                        ? JSON.stringify(c.args)
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}

function LegendDot({ className, label }: { className: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5 text-slate-400">
      <span className={`inline-block h-2.5 w-2.5 rounded-full ${className}`} />
      {label}
    </span>
  );
}

function ResultView({ result }: { result: EvalResult }) {
  const s = result.stats ?? {};
  return (
    <section className="glass p-5">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <CheckCircle2 className="h-4 w-4 text-emerald-300" />
        <h2 className="text-sm font-semibold text-slate-100">{result.title ?? "Results"}</h2>
        <div className="ml-auto flex flex-wrap gap-1.5 text-[11px]">
          {"passed" in s && (
            <Badge label={`${s.passed}/${s.total} passed`} tone="brand" />
          )}
          {"fixed" in s && <Badge label={`fixed ${s.fixed}`} tone="green" />}
          {"regressed" in s && (
            <Badge label={`regressed ${s.regressed}`} tone={s.regressed ? "red" : "muted"} />
          )}
          {result.regression !== undefined && (
            <Badge
              label={`regression ${result.regression ? "ON" : "off"}`}
              tone={result.regression ? "red" : "muted"}
            />
          )}
        </div>
      </div>

      {result.verdict && (
        <p className="mb-3 text-xs text-slate-300">{result.verdict}</p>
      )}

      <div className="space-y-4">
        {result.tables.map((t, i) => (
          <ResultTable key={i} table={t} />
        ))}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-white/10 pt-3 text-[11px] text-slate-400">
        <span className="flex items-center gap-1">
          <Gauge className="h-3.5 w-3.5" />
          {result.usage.calls} agent calls · {result.usage.total_tokens.toLocaleString()} tokens · $
          {result.usage.cost_usd.toFixed(4)}
        </span>
        {result.confident_link && (
          <a
            href={result.confident_link}
            target="_blank"
            rel="noreferrer"
            className="ml-auto flex items-center gap-1 text-brand-300 hover:text-brand-200"
          >
            Open full trace timeline in Confident AI
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        )}
      </div>
    </section>
  );
}

function ResultTable({ table }: { table: EvalTable }) {
  return (
    <div>
      <div className="mb-1.5 text-xs font-medium text-slate-300">{table.title}</div>
      <div className="overflow-x-auto rounded-lg border border-white/10">
        <table className="w-full text-left text-xs">
          <thead className="bg-white/[0.04] text-slate-400">
            <tr>
              {table.columns.map((c) => (
                <th key={c} className="px-3 py-2 font-medium">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row, i) => (
              <tr key={i} className="border-t border-white/5">
                {table.columns.map((c) => {
                  const v = row[c] ?? "";
                  const isStatus = ["status", "verdict", "result"].includes(c.toLowerCase());
                  return (
                    <td
                      key={c}
                      className={`px-3 py-2 ${
                        isStatus ? `font-semibold ${statusColor(v)}` : "text-slate-200"
                      }`}
                    >
                      {v}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Badge({
  label,
  tone,
}: {
  label: string;
  tone: "brand" | "green" | "red" | "muted";
}) {
  const tones: Record<string, string> = {
    brand: "bg-brand-500/15 text-brand-200",
    green: "bg-emerald-500/15 text-emerald-300",
    red: "bg-rose-500/15 text-rose-300",
    muted: "bg-white/[0.06] text-slate-300",
  };
  return <span className={`rounded px-2 py-0.5 ${tones[tone]}`}>{label}</span>;
}

function GoldensCard({
  goldens,
  custom,
  notice,
  onUploadClick,
  onReset,
}: {
  goldens: GoldenItem[];
  custom: boolean;
  notice: string | null;
  onUploadClick: () => void;
  onReset: () => void;
}) {
  return (
    <section className="glass p-5">
      <div className="mb-3 flex items-center gap-2">
        <Database className="h-4 w-4 text-brand-300" />
        <h3 className="text-sm font-semibold text-slate-100">Golden dataset</h3>
        <span
          className={`ml-auto rounded px-2 py-0.5 text-[10px] ${
            custom ? "bg-amber-500/15 text-amber-300" : "bg-white/[0.06] text-slate-300"
          }`}
        >
          {custom ? "custom" : "built-in"} · {goldens.length}
        </span>
      </div>

      <div className="flex gap-2">
        <button
          onClick={onUploadClick}
          className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.03] py-2 text-xs text-slate-200 transition hover:bg-white/[0.06]"
        >
          <Upload className="h-3.5 w-3.5" />
          Upload (.json / .csv)
        </button>
        {custom && (
          <button
            onClick={onReset}
            className="flex items-center justify-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-slate-200 transition hover:bg-white/[0.06]"
          >
            <RotateCcw className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {notice && <p className="mt-2 text-[11px] text-emerald-300">{notice}</p>}

      <p className="mt-2 text-[10px] leading-relaxed text-slate-500">
        Each row: <code>input</code> (required), optional <code>destination</code>,{" "}
        <code>difficulty</code>, <code>expected_tools</code>.
      </p>

      <ul className="mt-3 max-h-56 space-y-1.5 overflow-auto pr-1">
        {goldens.map((g, i) => (
          <li
            key={i}
            className="rounded-lg border border-white/5 bg-white/[0.02] px-2.5 py-1.5 text-[11px] text-slate-300"
          >
            <div className="flex items-center gap-1.5">
              {g.destination && (
                <span className="rounded bg-white/[0.06] px-1.5 py-0.5 text-[10px] text-slate-300">
                  {g.destination}
                </span>
              )}
              {g.difficulty === "trigger" && (
                <span className="rounded bg-rose-500/15 px-1.5 py-0.5 text-[10px] text-rose-300">
                  trigger
                </span>
              )}
            </div>
            <div className="mt-0.5 line-clamp-2 text-slate-400">{g.input}</div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ObservabilityDashboard({ obs }: { obs: Observability | null }) {
  const a = obs?.aggregate;
  const mcp = obs?.mcp;
  const series = obs?.pass_series ?? [];

  return (
    <section className="glass p-5">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Activity className="h-4 w-4 text-teal-300" />
        <h2 className="text-sm font-semibold text-slate-100">Observability dashboard</h2>
        <span className="text-[11px] text-slate-500">
          the headline metrics from Confident AI + Obot, in one place
        </span>
        <div className="ml-auto flex gap-2">
          <a
            href={obs?.confident_observatory ?? "https://app.confident-ai.com"}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1 rounded-lg border border-brand-400/30 bg-brand-500/10 px-2.5 py-1.5 text-[11px] text-brand-200 transition hover:bg-brand-500/20"
          >
            Confident AI <ExternalLink className="h-3 w-3" />
          </a>
          <a
            href={obs?.obot_url ?? "http://localhost:8080"}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1 rounded-lg border border-teal-400/30 bg-teal-500/10 px-2.5 py-1.5 text-[11px] text-teal-200 transition hover:bg-teal-500/20"
          >
            Obot gateway <ExternalLink className="h-3 w-3" />
          </a>
        </div>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-6">
        <Kpi icon={<FlaskConical className="h-3.5 w-3.5" />} label="Runs" value={a ? String(a.runs) : "—"} />
        <Kpi icon={<Gauge className="h-3.5 w-3.5" />} label="LLM calls" value={a ? a.calls.toLocaleString() : "—"} />
        <Kpi icon={<Wrench className="h-3.5 w-3.5" />} label="MCP calls" value={a ? a.tool_calls.toLocaleString() : "—"} tone="teal" />
        <Kpi icon={<Layers className="h-3.5 w-3.5" />} label="Tokens" value={a ? compact(a.total_tokens) : "—"} />
        <Kpi icon={<Coins className="h-3.5 w-3.5" />} label="Est. cost" value={a ? `$${a.cost_usd.toFixed(4)}` : "—"} tone="amber" />
        <Kpi icon={<Clock className="h-3.5 w-3.5" />} label="Avg run" value={a && a.avg_duration_s ? `${a.avg_duration_s}s` : "—"} />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        {/* Layer 1 pass-rate trend (Confident AI "Test Runs") */}
        <div className="rounded-lg border border-white/10 bg-white/[0.02] p-3">
          <div className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold text-slate-300">
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-300" />
            Layer 1 pass rate — by run
          </div>
          {series.length ? (
            <div className="flex h-28 items-end gap-1.5">
              {series.map((p, i) => {
                const pct = p.rate != null ? Math.round(p.rate * 100) : 0;
                return (
                  <div key={i} className="flex flex-1 flex-col items-center gap-1" title={`${p.passed}/${p.total} · regression ${p.regression ? "ON" : "off"}`}>
                    <div className="flex w-full items-end justify-center" style={{ height: 88 }}>
                      <div
                        className={`w-full rounded-t ${p.regression ? "bg-rose-400/70" : "bg-emerald-400/70"}`}
                        style={{ height: `${Math.max(pct, 4)}%` }}
                      />
                    </div>
                    <span className="text-[9px] text-slate-500">{pct}%</span>
                  </div>
                );
              })}
            </div>
          ) : (
            <Empty hint="Run Layer 1 to chart pass rate (regression on vs off)." />
          )}
          <div className="mt-2 flex gap-3 text-[9px] text-slate-500">
            <LegendDot className="bg-emerald-400" label="regression off" />
            <LegendDot className="bg-rose-400" label="regression on" />
          </div>
        </div>

        {/* MCP tool-call distribution (Obot gateway / Layer 4) */}
        <div className="rounded-lg border border-white/10 bg-white/[0.02] p-3">
          <div className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold text-slate-300">
            <Server className="h-3.5 w-3.5 text-teal-300" />
            MCP tool calls — by server &amp; tool {obs?.use_gateway ? "(via Obot gateway)" : ""}
          </div>
          {mcp && mcp.total > 0 ? (
            <ul className="space-y-1.5">
              {mcp.by_tool.slice(0, 7).map((t, i) => {
                const pct = Math.round((t.count / mcp.total) * 100);
                return (
                  <li key={i} className="text-[11px]">
                    <div className="mb-0.5 flex items-center gap-2">
                      <span className="font-mono text-teal-200">{t.tool}</span>
                      <span className="text-slate-500">{t.server}</span>
                      <span className="ml-auto text-slate-400">{t.count}</span>
                    </div>
                    <div className="h-1.5 w-full overflow-hidden rounded bg-white/[0.05]">
                      <div className="h-full rounded bg-teal-400/70" style={{ width: `${Math.max(pct, 3)}%` }} />
                    </div>
                  </li>
                );
              })}
            </ul>
          ) : (
            <Empty hint="Capture a live trace or run an eval to populate MCP call counts." />
          )}
        </div>
      </div>

      <p className="mt-3 text-[10px] leading-relaxed text-slate-500">
        Aggregated and <b className="text-slate-400">retained</b> across all runs on this server.
        The full trace-timeline waterfall, cross-session trends, and per-span latency live in
        Confident AI; the raw gateway audit lives in Obot — linked above.
      </p>
    </section>
  );
}

function RecentRunsCard({ obs }: { obs: Observability | null }) {
  return (
    <section className="glass p-5">
      <div className="mb-3 flex items-center gap-2">
        <Activity className="h-4 w-4 text-teal-300" />
        <h3 className="text-sm font-semibold text-slate-100">Recent runs</h3>
        <span className="ml-auto text-[10px] text-slate-500">retained</span>
      </div>
      {obs && obs.history.length > 0 ? (
        <ul className="max-h-[28rem] space-y-1.5 overflow-auto pr-1">
          {obs.history.map((h, i) => (
            <li
              key={i}
              className="rounded-lg border border-white/5 bg-white/[0.02] px-2.5 py-2 text-[11px]"
            >
              <div className="flex items-center gap-2">
                <span className="rounded bg-white/[0.06] px-1.5 py-0.5 text-[10px] text-slate-300">
                  {h.suite}
                </span>
                <span className="text-slate-300">{summarizeStats(h.stats)}</span>
                {h.confident_link && (
                  <a
                    href={h.confident_link}
                    target="_blank"
                    rel="noreferrer"
                    className="ml-auto text-brand-300 hover:text-brand-200"
                  >
                    <ExternalLink className="h-3 w-3" />
                  </a>
                )}
              </div>
              <div className="mt-1 flex items-center gap-3 text-[10px] text-slate-500">
                <span>${Number(h.usage?.cost_usd ?? 0).toFixed(4)}</span>
                <span>{Number(h.usage?.total_tokens ?? 0).toLocaleString()} tok</span>
                {h.duration_s != null && <span>{h.duration_s}s</span>}
                <span className="ml-auto">{relTime(h.ts)}</span>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <Empty hint="No runs yet — run a suite or capture a trace." />
      )}
    </section>
  );
}

function summarizeStats(stats: Record<string, number>): string {
  if ("passed" in stats) return `${stats.passed}/${stats.total} passed`;
  if ("candidate_pass" in stats)
    return `fixed ${stats.fixed} · regressed ${stats.regressed}`;
  return "";
}

function compact(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

function relTime(ts: number): string {
  const s = Math.max(0, Date.now() / 1000 - ts);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

function Kpi({
  icon,
  label,
  value,
  tone = "slate",
}: {
  icon: ReactNode;
  label: string;
  value: string;
  tone?: "slate" | "teal" | "amber";
}) {
  const tones: Record<string, string> = {
    slate: "text-slate-300",
    teal: "text-teal-300",
    amber: "text-amber-300",
  };
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.02] p-2.5">
      <div className={`flex items-center gap-1 text-[10px] ${tones[tone]}`}>
        {icon}
        {label}
      </div>
      <div className="mt-1 text-base font-semibold text-slate-100">{value}</div>
    </div>
  );
}

function Empty({ hint }: { hint: string }) {
  return (
    <div className="flex h-24 items-center justify-center rounded-lg border border-dashed border-white/10 px-3 text-center text-[11px] text-slate-500">
      {hint}
    </div>
  );
}
