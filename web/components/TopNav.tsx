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
    <header className="booking-header text-white">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-3 px-4 py-4">
        <span className="grid h-10 w-10 place-items-center rounded-lg bg-white/15 text-white ring-1 ring-white/25">
          <Compass className="h-5 w-5" />
        </span>
        <div>
          <h1 className="text-xl font-extrabold tracking-tight">Wander</h1>
          <p className="flex items-center gap-1.5 text-xs text-white/80">
            <Eye className="h-3 w-3" />
            Keeping Eyes on Your Agents — AV Data Hack Summit 2026
          </p>
        </div>

        <nav className="ml-auto flex items-center gap-1.5">
          {TABS.map(({ href, label, icon: Icon }) => {
            const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-sm font-semibold transition ${
                  active
                    ? "bg-white text-navy shadow-sm"
                    : "text-white/90 ring-1 ring-white/30 hover:bg-white/10"
                }`}
              >
                <Icon className="h-4 w-4" />
                {label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
