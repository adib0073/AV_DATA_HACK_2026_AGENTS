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
      <div className="mx-auto max-w-7xl px-4 pb-2">
        <h2 className="text-lg font-semibold text-slate-100">
          Eval <span className="gradient-text">Studio</span>
        </h2>
        <p className="mt-1 max-w-2xl text-sm text-slate-400">
          Run the multi-layer eval suite (end-to-end, component, shadow), upload your own
          golden dataset, and track aggregated observability — all in one place. Full
          trace timelines open in Confident AI.
        </p>
      </div>
      <EvalStudio />
    </main>
  );
}
