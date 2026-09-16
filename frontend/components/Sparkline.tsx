export function Sparkline({
  values, color, height = 88, strokeWidth = 1.6,
}: { values: (number | null)[]; color: string; height?: number; strokeWidth?: number }) {
  const w = 560;
  const real = values.filter((v): v is number => v != null);
  const min = Math.min(...real, 0);
  const max = Math.max(...real, 1);
  const pad = (max - min) * 0.08 || 1;
  const lo = min - pad;
  const hi = max + pad;

  // Break the line at null samples (comms down / no reading) instead of
  // drawing a fake connection across the gap or treating it as zero.
  const segments: string[][] = [[]];
  values.forEach((v, idx) => {
    if (v == null) {
      if (segments[segments.length - 1].length) segments.push([]);
      return;
    }
    const x = (idx / Math.max(1, values.length - 1)) * w;
    const y = height - ((v - lo) / (hi - lo || 1)) * height;
    segments[segments.length - 1].push(`${x.toFixed(1)},${Math.max(3, Math.min(height - 3, y)).toFixed(1)}`);
  });

  return (
    <svg
      viewBox={`0 0 ${w} ${height}`}
      preserveAspectRatio="none"
      className="w-full rounded-md border border-line bg-[#0e1117]"
      style={{ height }}
    >
      {segments.filter((s) => s.length).map((s, idx) => (
        <polyline key={idx} points={s.join(" ")} fill="none" stroke={color} strokeWidth={strokeWidth} />
      ))}
      {real.length === 0 && (
        <text x={w / 2} y={height / 2} textAnchor="middle" fontSize="10" fill="#5c6678" fontFamily="monospace">
          no data
        </text>
      )}
    </svg>
  );
}
