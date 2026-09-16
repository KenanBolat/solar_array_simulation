import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { Sidebar } from "@/components/Sidebar";
import { SimulationBanner } from "@/components/SimulationBanner";

export const metadata: Metadata = {
  title: "SAS Control Platform",
  description: "Solar Array Simulator monitoring and control — ground segment console",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <div className="flex h-screen flex-col">
            <SimulationBanner />
            <div className="flex min-h-0 flex-1">
              <Sidebar />
              <main className="grid-backdrop min-h-0 flex-1 overflow-y-auto">{children}</main>
            </div>
          </div>
        </Providers>
      </body>
    </html>
  );
}
