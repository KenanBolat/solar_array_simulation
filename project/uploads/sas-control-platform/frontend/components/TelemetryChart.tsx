"use client";

import ReactECharts from "echarts-for-react";
import type { Measurement } from "@/lib/types";

const COLORS = {
  voltage: "#22d3ee",
  current: "#34d399",
  power: "#a78bfa",
};

export function TelemetryChart({
  data,
  height = 260,
  series = ["voltage", "current", "power"],
  compact = false,
}: {
  data: Measurement[];
  height?: number;
  series?: Array<"voltage" | "current" | "power">;
  compact?: boolean;
}) {
  const times = data.map((d) => d.timestamp_utc);
  const mk = (key: "voltage" | "current" | "power") => {
    const field = key === "voltage" ? "voltage_v" : key === "current" ? "current_a" : "power_w";
    return {
      name:
        key === "voltage" ? "Voltage (V)" : key === "current" ? "Current (A)" : "Power (W)",
      type: "line" as const,
      smooth: true,
      showSymbol: false,
      yAxisIndex: key === "power" ? 1 : 0,
      lineStyle: { width: 1.6, color: COLORS[key] },
      areaStyle:
        key === "power"
          ? { color: "rgba(167,139,250,0.10)" }
          : key === "voltage"
            ? { color: "rgba(34,211,238,0.08)" }
            : undefined,
      data: data.map((d) => (d as unknown as Record<string, number>)[field]),
    };
  };

  const option = {
    backgroundColor: "transparent",
    grid: {
      left: compact ? 8 : 44,
      right: compact ? 8 : 44,
      top: compact ? 8 : 28,
      bottom: compact ? 8 : 24,
      containLabel: !compact,
    },
    tooltip: compact
      ? { show: false }
      : {
          trigger: "axis",
          backgroundColor: "#10151d",
          borderColor: "#232e3d",
          textStyle: { color: "#e6edf6", fontSize: 12 },
        },
    legend: compact
      ? { show: false }
      : {
          show: true,
          top: 0,
          right: 0,
          textStyle: { color: "#9aa7b8", fontSize: 11 },
          icon: "roundRect",
        },
    xAxis: {
      type: "category",
      data: times,
      show: !compact,
      axisLabel: {
        color: "#5f6b7c",
        fontSize: 10,
        formatter: (v: string) => v.slice(11, 19),
      },
      axisLine: { lineStyle: { color: "#232e3d" } },
      splitLine: { show: false },
    },
    yAxis: [
      {
        type: "value",
        show: !compact,
        axisLabel: { color: "#5f6b7c", fontSize: 10 },
        splitLine: { lineStyle: { color: "rgba(35,46,61,0.6)" } },
      },
      {
        type: "value",
        show: !compact,
        position: "right",
        axisLabel: { color: "#5f6b7c", fontSize: 10 },
        splitLine: { show: false },
      },
    ],
    series: series.map(mk),
    animationDuration: 300,
  };

  return (
    <ReactECharts
      option={option}
      style={{ height, width: "100%" }}
      opts={{ renderer: "canvas" }}
      notMerge
    />
  );
}
