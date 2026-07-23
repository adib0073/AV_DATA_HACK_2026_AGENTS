"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowUp, Bot, RotateCcw, Sparkles, User } from "lucide-react";

import { getConfig, resetUsage, streamPlan } from "@/lib/api";
import type {
  ActivityItem,
  AppConfig,
  ChatMessage,
  NodeEvent,
  TripState,
  Usage,
} from "@/lib/types";
import AgentActivity, { type Stage } from "./AgentActivity";
import Markdown from "./Markdown";
import TripDetails from "./TripDetails";
import UsageMeter from "./UsageMeter";

const EMPTY_USAGE: Usage = {
  calls: 0,
  input_tokens: 0,
  output_tokens: 0,
  total_tokens: 0,
  cost_usd: 0,
};

const STRIP_DEFAULT = ["planner", "flight", "hotel", "itinerary", "finalize"];
const STEP_TO_STAGE: Record<string, string> = {
  search_flights: "flight",
  search_hotels: "hotel",
  build_itinerary: "itinerary",
  book: "booking",
};

const EXAMPLES = [
  "Plan a 5-day relaxing trip to Bali for 2 from Mumbai in October, budget $2500 total.",
  "Explorer trip to Rome for 4 days, 1 traveler, from London, budget £1200.",
  "Plan and book a 4-day leisure trip to Dubai for 2 from Mumbai, budget $2200.",
];

export default function Chat() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [usage, setUsage] = useState<Usage>(EMPTY_USAGE);
  const [log, setLog] = useState<ActivityItem[]>([]);
  const [seen, setSeen] = useState<string[]>([]);
  const [planExpected, setPlanExpected] = useState<string[] | null>(null);
  const [labels, setLabels] = useState<Record<string, string>>({});
  const [running, setRunning] = useState(false);
  const [input, setInput] = useState("");

  const idRef = useRef(0);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getConfig()
      .then((c) => {
        setConfig(c);
        setLabels(c.nodes ?? {});
      })
      .catch(() => void 0);
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, log, running]);

  const label = (key: string) => labels[key] ?? key;

  const stages: Stage[] = useMemo(() => {
    const keys = planExpected ?? STRIP_DEFAULT;
    return keys.map((key) => {
      let status: Stage["status"] = "pending";
      if (seen.includes(key)) status = "done";
      else if (running) {
        const firstUnseen = keys.find((k) => !seen.includes(k));
        status = firstUnseen === key ? "active" : "pending";
      } else status = "skipped";
      return { key, label: label(key), status };
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [planExpected, seen, running, labels]);

  function handleNode(ev: NodeEvent) {
    setSeen((s) => (s.includes(ev.node) ? s : [...s, ev.node]));

    if (ev.node === "planner") {
      const plan = (ev.data?.plan as string[]) ?? [];
      const expected = [
        "planner",
        ...plan.map((p) => STEP_TO_STAGE[p]).filter(Boolean),
        "finalize",
      ];
      setPlanExpected([...new Set(expected)]);
    }

    if (ev.node === "supervisor") return; // keep the log focused on real agents

    const detail = nodeDetail(ev);
    setLog((l) => [
      ...l,
      { id: idRef.current++, node: ev.node, label: ev.label, detail, ts: Date.now() },
    ]);
  }

  async function send(text: string) {
    const msg = text.trim();
    if (!msg || running) return;

    setMessages((m) => [
      ...m,
      { id: `u-${Date.now()}`, role: "user", content: msg },
    ]);
    setInput("");
    setLog([]);
    setSeen([]);
    setPlanExpected(null);
    setRunning(true);

    let finalState: TripState | undefined;
    let finalText = "";

    await streamPlan(msg, {
      onPipeline: (l) => setLabels((prev) => ({ ...prev, ...l })),
      onNode: handleNode,
      onUsage: (u) => setUsage(u),
      onFinal: (ev) => {
        finalState = ev.state;
        finalText = ev.response;
      },
      onError: (message) => {
        setMessages((m) => [
          ...m,
          {
            id: `a-${Date.now()}`,
            role: "assistant",
            content: message,
            error: true,
          },
        ]);
      },
    });

    if (finalText) {
      setMessages((m) => [
        ...m,
        {
          id: `a-${Date.now()}`,
          role: "assistant",
          content: finalText,
          state: finalState,
        },
      ]);
    }
    setRunning(false);
  }

  async function onReset() {
    await resetUsage().catch(() => void 0);
    setUsage(EMPTY_USAGE);
  }

  return (
    <div className="mx-auto grid max-w-7xl gap-5 px-4 pb-10 pt-6 lg:grid-cols-[1fr_380px]">
      {/* Conversation */}
      <section className="glass flex min-h-[70vh] flex-col overflow-hidden">
        <div className="flex-1 space-y-4 overflow-y-auto p-5">
          {messages.length === 0 && <EmptyState onPick={send} />}
          {messages.map((m) => (
            <MessageBubble key={m.id} message={m} />
          ))}
          {running && messages[messages.length - 1]?.role === "user" && (
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <span className="grid h-8 w-8 place-items-center rounded-full bg-brand-50 text-brand-600">
                <Bot className="h-4 w-4" />
              </span>
              <span className="shimmer rounded-lg px-2 py-1">
                Coordinating agents…
              </span>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Composer */}
        <div className="border-t border-line p-4">
          <div className="flex items-end gap-2 rounded-xl border border-slate-300 bg-white p-2 shadow-sm focus-within:border-brand-500 focus-within:ring-2 focus-within:ring-brand-500/20">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send(input);
                }
              }}
              rows={1}
              placeholder="Describe your trip — destination, dates, travelers, budget, vibe…"
              className="max-h-40 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm text-ink placeholder:text-slate-400 focus:outline-none"
            />
            <button
              onClick={() => send(input)}
              disabled={running || !input.trim()}
              className="grid h-9 w-9 place-items-center rounded-lg bg-brand-500 text-white transition hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-40"
              aria-label="Send"
            >
              <ArrowUp className="h-4 w-4" />
            </button>
          </div>
        </div>
      </section>

      {/* Right rail */}
      <aside className="space-y-5">
        <AgentActivity stages={stages} log={log} running={running} />
        <UsageMeter usage={usage} config={config} />
        <button
          onClick={onReset}
          className="flex w-full items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white py-2 text-xs font-medium text-slate-600 transition hover:bg-slate-50"
        >
          <RotateCcw className="h-3.5 w-3.5" />
          Reset session usage
        </button>
      </aside>
    </div>
  );
}

function nodeDetail(ev: NodeEvent): string | undefined {
  const d = ev.data ?? {};
  if (ev.node === "planner") {
    const plan = (d.plan as string[]) ?? [];
    return plan.length ? `Plan: ${plan.join(" → ")}` : undefined;
  }
  if (ev.node === "flight") {
    const f = d.selected_flight as { airline?: string; price?: number } | null;
    return f ? `Picked ${f.airline ?? "a flight"} · $${Math.round(f.price ?? 0)}` : "Searched flights";
  }
  if (ev.node === "hotel") {
    const h = d.selected_hotel as { name?: string; price?: number } | null;
    return h ? `Picked ${h.name ?? "a hotel"} · $${Math.round(h.price ?? 0)}/night` : "Searched hotels";
  }
  if (ev.node === "itinerary") {
    const it = d.itinerary as { activities?: unknown[] } | null;
    const n = it?.activities?.length ?? 0;
    return n ? `${n}-day itinerary built` : "Itinerary built";
  }
  if (ev.node === "booking") {
    return "Reservations confirmed";
  }
  if (ev.node === "finalize") {
    return "Trip plan ready";
  }
  return undefined;
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
      <span
        className={`grid h-8 w-8 shrink-0 place-items-center rounded-full ${
          isUser ? "bg-slate-100 text-slate-600" : "bg-brand-50 text-brand-600"
        }`}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </span>
      <div className={`min-w-0 max-w-[85%] ${isUser ? "text-right" : ""}`}>
        <div
          className={`inline-block rounded-2xl px-4 py-2.5 text-sm ${
            isUser
              ? "whitespace-pre-wrap bg-brand-500 text-white"
              : message.error
                ? "whitespace-pre-wrap border border-rose-200 bg-rose-50 text-rose-700"
                : "w-full border border-slate-200 bg-white text-slate-800"
          }`}
        >
          {isUser || message.error ? (
            message.content
          ) : (
            <Markdown>{message.content}</Markdown>
          )}
        </div>
        {message.state && (
          <div className="text-left">
            <TripDetails state={message.state} />
          </div>
        )}
      </div>
    </div>
  );
}

function EmptyState({ onPick }: { onPick: (s: string) => void }) {
  return (
    <div className="grid h-full place-items-center py-10 text-center animate-fade-up">
      <div>
        <div className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-2xl bg-brand-50 text-brand-600">
          <Sparkles className="h-7 w-7" />
        </div>
        <h2 className="text-lg font-bold text-ink">
          Where would you like to go?
        </h2>
        <p className="mx-auto mt-1 max-w-md text-sm text-slate-500">
          Tell me your destination, dates or duration, travelers, budget and the
          kind of trip you want. The agents will plan it — and you can watch them
          work on the right.
        </p>
        <div className="mt-5 flex flex-wrap justify-center gap-2">
          {EXAMPLES.map((e) => (
            <button
              key={e}
              onClick={() => onPick(e)}
              className="rounded-full border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-600 transition hover:border-brand-400 hover:bg-brand-50 hover:text-brand-700"
            >
              {e.length > 52 ? e.slice(0, 52) + "…" : e}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
