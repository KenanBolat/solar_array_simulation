export function Sparkline({
  values, color, height = 88, strokeWidth = 1.6,
}: { values: number[]; color: string; height?: number; strokeWidth?: number }) {
  const w = 560;
  const min = Math.min(...values, 0);
  const max = Math.max(...values, 1);
  const pad = (max - min) * 0.08 || 1;
  const lo = min - pad;
  const hi = max + pad;
  const points = values
    .map((v, idx) => {
      const x = (idx / Math.max(1, values.length - 1)) * w;
      const y = height - ((v - lo) / (hi - lo || 1)) * height;
      return `${x.toFixed(1)},${Math.max(3, Math.min(height - 3, y)).toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg
      viewBox={`0 0 ${w} ${height}`}
      preserveAspectRatio="none"
      className="w-full rounded-md border border-line bg-[#0e1117]"
      style={{ height }}
    >
      <polyline points={points} fill="none" stroke={color} strokeWidth={strokeWidth} />
    </svg>
  );
}
