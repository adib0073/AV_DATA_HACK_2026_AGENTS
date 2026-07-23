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
  planner: "text-brand-600",
  supervisor: "text-slate-500",
  flight: "text-sky-600",
  hotel: "text-emerald-600",
  itinerary: "text-amber-600",
  booking: "text-fuchsia-600",
  finalize: "text-teal-500",
};
