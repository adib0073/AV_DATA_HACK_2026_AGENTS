"use client";

import { BedDouble, CalendarCheck2, Map, Plane, Star } from "lucide-react";
import type { TripState } from "@/lib/types";

export default function TripDetails({ state }: { state: TripState }) {
  const flight = state.selected_flight;
  const hotel = state.selected_hotel;
  const days = state.itinerary?.activities ?? [];
  const booking = state.booking;

  const hasAny = flight || hotel || days.length || booking;
  if (!hasAny) return null;

  return (
    <div className="mt-3 grid gap-3 sm:grid-cols-2">
      {flight && (
        <Card title="Flight" icon={<Plane className="h-4 w-4 text-sky-300" />}>
          <div className="flex items-baseline justify-between">
            <span className="font-medium text-slate-100">
              {flight.airline ?? "Flight"}
            </span>
            <span className="gradient-text font-semibold">
              {money(flight.price, flight.currency)}
            </span>
          </div>
          <Meta>
            {flight.flight_id} · {flight.stops ? `${flight.stops} stop` : "non-stop"}
            {flight.duration_hours ? ` · ${flight.duration_hours}h` : ""}
            {flight.depart ? ` · dep ${flight.depart}` : ""}
          </Meta>
        </Card>
      )}

      {hotel && (
        <Card title="Hotel" icon={<BedDouble className="h-4 w-4 text-emerald-300" />}>
          <div className="flex items-baseline justify-between">
            <span className="font-medium text-slate-100 truncate">{hotel.name}</span>
            <span className="gradient-text font-semibold">
              {money(hotel.price, hotel.currency)}
              <span className="text-xs text-slate-400">/night</span>
            </span>
          </div>
          <Meta>
            <span className="inline-flex items-center gap-1">
              <Star className="h-3 w-3 text-amber-300" />
              {hotel.rating ?? hotel.stars}
            </span>
            {hotel.neighborhood ? ` · ${hotel.neighborhood}` : ""}
            {hotel.style ? ` · ${hotel.style}` : ""}
          </Meta>
        </Card>
      )}

      {days.length > 0 && (
        <Card
          title="Itinerary"
          icon={<Map className="h-4 w-4 text-amber-300" />}
          className="sm:col-span-2"
        >
          <div className="grid gap-2 sm:grid-cols-2">
            {days.map((d) => (
              <div
                key={d.day}
                className="rounded-lg border border-white/10 bg-white/[0.02] p-2.5"
              >
                <div className="text-xs font-semibold text-brand-200">
                  Day {d.day}
                </div>
                <ul className="mt-1 space-y-0.5 text-xs text-slate-300">
                  {d.morning && <li>🌅 {d.morning}</li>}
                  {d.afternoon && <li>☀️ {d.afternoon}</li>}
                  {d.evening && <li>🌙 {d.evening}</li>}
                </ul>
              </div>
            ))}
          </div>
        </Card>
      )}

      {booking && (
        <Card
          title="Booking"
          icon={<CalendarCheck2 className="h-4 w-4 text-fuchsia-300" />}
          className="sm:col-span-2"
        >
          <p className="text-sm text-emerald-200">{booking.summary}</p>
        </Card>
      )}
    </div>
  );
}

function Card({
  title,
  icon,
  children,
  className = "",
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-xl border border-white/10 bg-white/[0.03] p-3.5 ${className}`}
    >
      <div className="mb-2 flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-slate-400">
        {icon}
        {title}
      </div>
      {children}
    </div>
  );
}

function Meta({ children }: { children: React.ReactNode }) {
  return <p className="mt-1 text-xs text-slate-400">{children}</p>;
}

function money(v?: number, currency = "USD") {
  if (v == null) return "—";
  const sym = currency === "USD" ? "$" : `${currency} `;
  return `${sym}${Math.round(v).toLocaleString()}`;
}
