import {
  BedDouble,
  CalendarCheck2,
  ClipboardList,
  Map,
  Plane,
  Sparkles,
  Workflow,
  type LucideIcon,
} from "lucide-react";

export const NODE_ICON: Record<string, LucideIcon> = {
  planner: ClipboardList,
  supervisor: Workflow,
  flight: Plane,
  hotel: BedDouble,
  itinerary: Map,
  booking: CalendarCheck2,
  finalize: Sparkles,
};

export const NODE_ACCENT: Record<string, string> = {
  planner: "text-brand-300",
  supervisor: "text-slate-300",
  flight: "text-sky-300",
  hotel: "text-emerald-300",
  itinerary: "text-amber-300",
  booking: "text-fuchsia-300",
  finalize: "text-teal-300",
};
