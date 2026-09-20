import { Sidebar } from "@/components/Sidebar";
import { TopBar } from "@/components/TopBar";
import { HeaderProvider } from "@/lib/header-context";
import { AppUiProvider } from "@/lib/ui-context";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="flex min-h-screen bg-eng-grid bg-eng-grid"
      style={{ backgroundColor: "#0b0d11" }}
    >
      <HeaderProvider>
        <AppUiProvider>
          <Sidebar />
          {/* min-w-0 lets this column shrink below its content width; without it a
              wide child (the scenario canvas) pushes the whole page sideways. */}
          <div className="flex h-screen min-w-0 flex-1 flex-col">
            <TopBar />
            <div className="min-w-0 flex-1 overflow-auto">{children}</div>
          </div>
        </AppUiProvider>
      </HeaderProvider>
    </div>
  );
}
