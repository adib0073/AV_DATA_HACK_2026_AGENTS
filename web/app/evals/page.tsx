import EvalStudio from "@/components/EvalStudio";
import TopNav from "@/components/TopNav";

export const metadata = {
  title: "Eval Studio · Wander",
  description: "Run the multi-layer eval suite, manage goldens, and watch observability.",
};

export default function EvalsPage() {
  return (
    <main className="min-h-screen">
      <TopNav />
      <div className="mx-auto max-w-7xl px-4 pb-2 pt-6">
        <h2 className="text-2xl font-extrabold tracking-tight text-ink">
          Eval <span className="gradient-text">Studio</span>
        </h2>
        <p className="mt-1 max-w-2xl text-sm text-slate-500">
          Run the multi-layer eval suite (end-to-end, component, shadow), upload your own
          golden dataset, and track aggregated observability — all in one place. Full
          trace timelines open in Langfuse.
        </p>
      </div>
      <EvalStudio />
    </main>
  );
}
