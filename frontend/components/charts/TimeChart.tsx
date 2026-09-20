"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useChartSync } from "./ChartSync";

/** Categorical identity colours, stepped for this app's dark chart surface
 *  (#0e1117) and validated: adjacent CVD ΔE 8.4, normal-vision ΔE 19.3, all
 *  ≥3:1 contrast. Assigned in fixed order and keyed to the series, never
 *  cycled or reassigned when the selection changes, so a channel keeps its
 *  colour as others come and go. */
export const SERIES_COLORS = [
  "#3987e5", "#d95926", "#199e70", "#c98500",
  "#d55181", "#008300", "#9085e9", "#e66767",
];

export function seriesColor(index: number) {
  return SERIES_COLORS[index % SERIES_COLORS.length];
}

export interface ChartSeries {
  key: string;
  label: string;
  color: string;
  ts: number[];                 // epoch ms, ascending
  values: (number | null)[];    // null = no reading (comms down)
}

const SURFACE = "#0e1117";
const GRID = "#1b2230";
const AXIS_TEXT = "#5c6678";
const INK = "#e6eaf2";

const PAD = { top: 10, right: 58, bottom: 20, left: 8 };

function fmtClock(ts: number) {
  const d = new Date(ts);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

/** yymmdd hh:mm:ss — the format asked for in the readout. */
function fmtStamp(ts: number) {
  const d = new Date(ts);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${String(d.getFullYear()).slice(2)}${p(d.getMonth() + 1)}${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

function niceTicks(lo: number, hi: number, count = 4): number[] {
  if (!isFinite(lo) || !isFinite(hi) || hi <= lo) return [lo];
  const raw = (hi - lo) / count;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const norm = raw / mag;
  const step = (norm >= 5 ? 10 : norm >= 2 ? 5 : norm >= 1 ? 2 : 1) * mag;
  const out: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-6; v += step) out.push(+v.toFixed(10));
  return out;
}

/** Nearest sample at or around a time, with the gap rule: a null sample breaks
 *  the line rather than being drawn as zero or bridged. */
function sampleAt(s: ChartSeries, ts: number): { ts: number; value: number | null } | null {
  if (!s.ts.length) return null;
  let lo = 0, hi = s.ts.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (s.ts[mid] < ts) lo = mid + 1; else hi = mid;
  }
  const cand = [lo - 1, lo].filter((i) => i >= 0 && i < s.ts.length);
  let best = cand[0];
  for (const i of cand) if (Math.abs(s.ts[i] - ts) < Math.abs(s.ts[best] - ts)) best = i;
  return { ts: s.ts[best], value: s.values[best] ?? null };
}

export function TimeChart({
  title, unit, decimals = 2, series, height = 132, sync = true, showLegend,
}: {
  title: string;
  unit: string;
  decimals?: number;
  series: ChartSeries[];
  height?: number;
  sync?: boolean;
  showLegend?: boolean;
}) {
  const [fullscreen, setFullscreen] = useState(false);
  // In fullscreen a chart stands alone, so it keeps its own hover/zoom rather
  // than driving the charts hidden behind it.
  const { hoverTs, setHoverTs, domain, setDomain } = useChartSync(sync && !fullscreen);
  const [drag, setDrag] = useState<{ from: number; to: number } | null>(null);
  const [box, setBox] = useState({ w: 720, h: height });
  const wrapRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const plotH = box.h - PAD.top - PAD.bottom;
  const plotW = box.w - PAD.left - PAD.right;

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => {
      const cr = e.contentRect;
      setBox({ w: Math.max(240, cr.width), h: Math.max(90, cr.height) });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [fullscreen]);

  useEffect(() => {
    if (!fullscreen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setFullscreen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [fullscreen]);

  // ---- scales -------------------------------------------------------------
  const allTs = series.flatMap((s) => s.ts);
  const fullLo = allTs.length ? Math.min(...allTs) : 0;
  const fullHi = allTs.length ? Math.max(...allTs) : 1;
  const [tLo, tHi] = domain ?? [fullLo, fullHi];
  const tSpan = tHi - tLo || 1;

  const visible = series.flatMap((s) =>
    s.values.filter((v, i): v is number => v != null && s.ts[i] >= tLo && s.ts[i] <= tHi));
  const vMinRaw = visible.length ? Math.min(...visible) : 0;
  const vMaxRaw = visible.length ? Math.max(...visible) : 1;
  const vPad = (vMaxRaw - vMinRaw) * 0.12 || Math.max(Math.abs(vMaxRaw) * 0.1, 0.5);
  const vLo = vMinRaw - vPad;
  const vHi = vMaxRaw + vPad;

  const x = (ts: number) => PAD.left + ((ts - tLo) / tSpan) * plotW;
  const y = (v: number) => PAD.top + plotH - ((v - vLo) / (vHi - vLo || 1)) * plotH;
  const tsAt = (px: number) => tLo + ((px - PAD.left) / (plotW || 1)) * tSpan;

  // ---- pointer ------------------------------------------------------------
  const localX = (e: React.PointerEvent) => {
    const r = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
    return ((e.clientX - r.left) / r.width) * box.w;
  };

  const onMove = (e: React.PointerEvent) => {
    const px = localX(e);
    setHoverTs(tsAt(Math.max(PAD.left, Math.min(PAD.left + plotW, px))));
    if (drag) setDrag({ ...drag, to: px });
  };
  const onDown = (e: React.PointerEvent) => {
    const px = localX(e);
    (e.currentTarget as SVGSVGElement).setPointerCapture(e.pointerId);
    setDrag({ from: px, to: px });
  };
  const onUp = () => {
    if (drag && Math.abs(drag.to - drag.from) > 8) {
      const a = tsAt(Math.min(drag.from, drag.to));
      const b = tsAt(Math.max(drag.from, drag.to));
      setDomain([a, b]);
    }
    setDrag(null);
  };
  const resetZoom = () => setDomain(null);

  // ---- PNG ----------------------------------------------------------------
  const savePng = useCallback(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const clone = svg.cloneNode(true) as SVGSVGElement;
    clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    clone.querySelectorAll("[data-transient]").forEach((n) => n.remove());
    const scale = 2;
    const blob = new Blob([new XMLSerializer().serializeToString(clone)], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = box.w * scale;
      canvas.height = box.h * scale;
      const ctx = canvas.getContext("2d");
      if (ctx) {
        ctx.fillStyle = SURFACE;
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        const a = document.createElement("a");
        a.download = `${title.replace(/[^\w.-]+/g, "_")}_${fmtStamp(Date.now()).replace(/[: ]/g, "")}.png`;
        a.href = canvas.toDataURL("image/png");
        a.click();
      }
      URL.revokeObjectURL(url);
    };
    img.onerror = () => URL.revokeObjectURL(url);
    img.src = url;
  }, [box.w, box.h, title]);

  // ---- readout ------------------------------------------------------------
  const readout = hoverTs != null
    ? series.map((s) => ({ s, hit: sampleAt(s, hoverTs) })).filter((r) => r.hit)
    : [];
  const hoverX = hoverTs != null ? x(hoverTs) : null;
  const inPlot = hoverX != null && hoverX >= PAD.left - 1 && hoverX <= PAD.left + plotW + 1;
  const stampTs = readout.length ? readout[0].hit!.ts : hoverTs;

  const vTicks = niceTicks(vLo, vHi, 3);
  const tTicks = [tLo, tLo + tSpan / 2, tHi];
  const legend = showLegend ?? series.length > 1;

  const chart = (
    // Only the fullscreen overlay gives this a height to fill; inline the
    // plot is sized by the `height` prop, so it must not flex to 0 there.
    <div className={fullscreen ? "relative flex min-h-0 flex-1 flex-col" : "relative flex flex-col"}>
      <div className="mb-1 flex flex-none items-center justify-between gap-2">
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-[9.5px] uppercase tracking-wider text-faint">{title} · {unit.trim()}</span>
          {domain && (
            <button onClick={resetZoom} className="rounded border border-cyan/40 px-1.5 py-0.5 text-[9px] font-semibold text-cyan">
              reset zoom
            </button>
          )}
        </div>
        <div className="flex items-center gap-1">
          {legend && (
            <div className="mr-1.5 flex flex-wrap items-center gap-2">
              {series.map((s) => (
                <span key={s.key} className="flex items-center gap-1">
                  <svg width="12" height="3" aria-hidden><line x1="0" y1="1.5" x2="12" y2="1.5" stroke={s.color} strokeWidth="2.5" /></svg>
                  <span className="font-mono text-[9.5px] text-muted">{s.label}</span>
                </span>
              ))}
            </div>
          )}
          <IconBtn title="Save as PNG" onClick={savePng}>PNG</IconBtn>
          <IconBtn title={fullscreen ? "Exit full screen (Esc)" : "Full screen"} onClick={() => setFullscreen((f) => !f)}>
            {fullscreen ? "✕" : "⛶"}
          </IconBtn>
        </div>
      </div>

      <div ref={wrapRef} className={fullscreen ? "relative min-h-0 flex-1" : "relative w-full"}
        style={fullscreen ? undefined : { height }}>
        <svg
          ref={svgRef}
          viewBox={`0 0 ${box.w} ${box.h}`}
          width={box.w}
          height={box.h}
          className="absolute inset-0 h-full w-full touch-none rounded-md"
          style={{ background: SURFACE, border: "1px solid #1b2230", cursor: drag ? "ew-resize" : "crosshair" }}
          onPointerMove={onMove}
          onPointerLeave={() => { setHoverTs(null); setDrag(null); }}
          onPointerDown={onDown}
          onPointerUp={onUp}
          onDoubleClick={resetZoom}
        >
          {/* value grid + right-hand axis labels, in units */}
          {vTicks.map((t) => (
            <g key={t}>
              <line x1={PAD.left} y1={y(t)} x2={PAD.left + plotW} y2={y(t)} stroke={GRID} strokeWidth="1" />
              <text x={PAD.left + plotW + 6} y={y(t) + 3.5} fontSize="9.5" fontFamily="monospace" fill={AXIS_TEXT}>
                {t.toFixed(decimals)}{unit}
              </text>
            </g>
          ))}
          {/* time axis */}
          {tTicks.map((t, i) => (
            <text key={i} x={i === 0 ? PAD.left : i === 1 ? PAD.left + plotW / 2 : PAD.left + plotW}
              y={box.h - 6} fontSize="9.5" fontFamily="monospace" fill={AXIS_TEXT}
              textAnchor={i === 0 ? "start" : i === 1 ? "middle" : "end"}>
              {allTs.length ? fmtClock(t) : ""}
            </text>
          ))}

          {series.map((s) => {
            // break the line at nulls instead of bridging or drawing zero
            const segs: string[][] = [[]];
            s.ts.forEach((ts, i) => {
              const v = s.values[i];
              if (v == null || ts < tLo || ts > tHi) {
                if (segs[segs.length - 1].length) segs.push([]);
                return;
              }
              segs[segs.length - 1].push(`${x(ts).toFixed(1)},${y(v).toFixed(1)}`);
            });
            return segs.filter((p) => p.length > 1).map((p, i) => (
              <polyline key={`${s.key}-${i}`} points={p.join(" ")} fill="none"
                stroke={s.color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
            ));
          })}

          {!allTs.length && (
            <text x={box.w / 2} y={box.h / 2} textAnchor="middle" fontSize="10" fontFamily="monospace" fill={AXIS_TEXT}>
              no samples in this range
            </text>
          )}

          {/* crosshair + hovered points */}
          {inPlot && hoverX != null && (
            <g data-transient>
              <line x1={hoverX} y1={PAD.top} x2={hoverX} y2={PAD.top + plotH} stroke="#8a95a8" strokeWidth="1" strokeDasharray="3 3" />
              {readout.map(({ s, hit }) => hit!.value != null && (
                <circle key={s.key} cx={x(hit!.ts)} cy={y(hit!.value)} r="3.5"
                  fill={s.color} stroke={SURFACE} strokeWidth="1.5" />
              ))}
            </g>
          )}

          {/* drag-to-zoom band */}
          {drag && Math.abs(drag.to - drag.from) > 2 && (
            <rect data-transient x={Math.min(drag.from, drag.to)} y={PAD.top}
              width={Math.abs(drag.to - drag.from)} height={plotH} fill="#2dd4ee18" stroke="#2dd4ee66" strokeWidth="1" />
          )}
        </svg>

        {/* readout: value leads, series name follows */}
        {inPlot && readout.length > 0 && !drag && (
          <div
            className="pointer-events-none absolute z-10 rounded-md border border-line2 px-2 py-1.5 shadow-[0_8px_24px_rgba(0,0,0,0.5)]"
            style={{
              background: "#141a24f2",
              // the SVG renders 1:1 with its viewBox, so hoverX is already in px
              left: Math.min(Math.max(8, hoverX! + 12), Math.max(8, box.w - 172)),
              top: 6,
              minWidth: 150,
            }}
          >
            <div className="mb-1 font-mono text-[9.5px] text-faint">{stampTs != null ? fmtStamp(stampTs) : ""}</div>
            {readout.map(({ s, hit }) => (
              <div key={s.key} className="flex items-baseline justify-between gap-3">
                <span className="flex items-center gap-1.5">
                  <svg width="10" height="3" aria-hidden><line x1="0" y1="1.5" x2="10" y2="1.5" stroke={s.color} strokeWidth="2.5" /></svg>
                  <span className="font-mono text-[9.5px] text-muted">{s.label}</span>
                </span>
                <span className="font-mono text-[11.5px] font-semibold" style={{ color: INK }}>
                  {hit!.value != null ? `${hit!.value.toFixed(decimals)}${unit}` : "no reading"}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
      {!fullscreen && (
        <div className="mt-0.5 flex-none font-mono text-[8.5px] text-faint/70">drag to zoom · double-click to reset</div>
      )}
    </div>
  );

  if (!fullscreen) return chart;

  return (
    <>
      <div className="relative" style={{ height }} />
      <div className="fixed inset-0 z-[70] flex flex-col bg-[#05070af2] p-5">
        <div className="mb-2 flex flex-none items-center justify-between">
          <span className="text-[13px] font-semibold text-ink">{title}</span>
          <button onClick={() => setFullscreen(false)}
            className="rounded-md border border-line2 bg-panel2 px-2.5 py-1 text-[11px] font-semibold text-ink">
            Close (Esc)
          </button>
        </div>
        <div className="flex min-h-0 flex-1 flex-col rounded-lg border border-line bg-panel p-3">{chart}</div>
      </div>
    </>
  );
}

function IconBtn({ children, title, onClick }: { children: React.ReactNode; title: string; onClick: () => void }) {
  return (
    <button title={title} onClick={onClick}
      className="rounded border border-line2 bg-panel2 px-1.5 py-0.5 font-mono text-[9.5px] font-semibold text-muted hover:text-ink">
      {children}
    </button>
  );
}
