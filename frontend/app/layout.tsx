import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Solar Array Simulator Control Platform",
  description: "Monitor, control, and automate solar array simulator test scenarios.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="font-sans bg-bg text-ink antialiased">{children}</body>
    </html>
  );
}
