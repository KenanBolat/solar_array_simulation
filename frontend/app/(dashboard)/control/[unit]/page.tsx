import { ControlScreen } from "@/components/control/ControlScreen";

export default async function ControlPage({ params }: { params: Promise<{ unit: string }> }) {
  const { unit } = await params;
  return <ControlScreen unitName={decodeURIComponent(unit)} />;
}
