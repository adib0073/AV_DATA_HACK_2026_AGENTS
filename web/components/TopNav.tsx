"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Compass, Eye, FlaskConical } from "lucide-react";

const TABS = [
  { href: "/", label: "Planner", icon: Compass },
  { href: "/evals", label: "Eval Studio", icon: FlaskConical },
];

export default function TopNav() {
  const pathname = usePathname();
  return (
    <header className="mx-auto flex max-w-7xl flex-wrap items-center gap-3 px-4 py-6">
      <span className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-brand-500 to-teal-500 text-white shadow-lg">
        <Compass className="h-5 w-5" />
      </span>
      <div>
        <h1 className="text-xl font-bold tracking-tight">
          Wander <span className="gradient-text">· agentic trip planner</span>
        </h1>
        <p className="flex items-center gap-1.5 text-xs text-slate-400">
          <Eye className="h-3 w-3" />
          Keeping Eyes on Your Agents — AV Data Hack Summit 2026
        </p>
      </div>

      <nav className="ml-auto flex items-center gap-1 rounded-full border border-white/10 bg-white/[0.03] p-1">
        {TABS.map(({ href, label, icon: Icon }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition ${
                active
                  ? "bg-brand-500 text-white shadow"
                  : "text-slate-300 hover:bg-white/[0.06]"
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
