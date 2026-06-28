import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Wander · Agentic Trip Planner",
  description:
    "An agentic travel planner you can watch — Keeping Eyes on Your Agents (AV Data Hack Summit 2026)",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
