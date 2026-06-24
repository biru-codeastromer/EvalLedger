"use client";

import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { ContaminationReport } from "@/lib/types";

interface ChartColors {
  text: string;
  textDim: string;
  border: string;
  borderLight: string;
  accent: string;
  surface: string;
}

const FALLBACK_COLORS: ChartColors = {
  text: "#1a1916",
  textDim: "#4a4740",
  border: "#d4cfc6",
  borderLight: "#e0dbd2",
  accent: "#1a1916",
  surface: "#edeae3"
};

function readColors(): ChartColors {
  if (typeof window === "undefined") {
    return FALLBACK_COLORS;
  }
  const styles = getComputedStyle(document.documentElement);
  const read = (name: string, fallback: string) => styles.getPropertyValue(name).trim() || fallback;
  return {
    text: read("--text", FALLBACK_COLORS.text),
    textDim: read("--text-dim", FALLBACK_COLORS.textDim),
    border: read("--border", FALLBACK_COLORS.border),
    borderLight: read("--border-light", FALLBACK_COLORS.borderLight),
    accent: read("--accent", FALLBACK_COLORS.accent),
    surface: read("--surface", FALLBACK_COLORS.surface)
  };
}

interface OverlapDatum {
  name: string;
  overlap: number;
}

function OverlapTooltip({
  active,
  payload,
  colors
}: {
  active?: boolean;
  payload?: Array<{ payload: OverlapDatum }>;
  colors: ChartColors;
}) {
  if (!active || !payload || payload.length === 0) {
    return null;
  }
  const datum = payload[0].payload;
  return (
    <div
      className="rounded-sm px-3 py-2 shadow-sm"
      style={{ background: colors.surface, border: `1px solid ${colors.border}` }}
    >
      <div className="mono mb-1" style={{ color: colors.textDim }}>
        {datum.name}
      </div>
      <div className="ui-copy text-[14px] font-medium" style={{ color: colors.text }}>
        {datum.overlap.toFixed(1)}% overlap
      </div>
    </div>
  );
}

export function OverlapVisualizer({ reports }: { reports: ContaminationReport[] }) {
  const [colors, setColors] = useState<ChartColors>(FALLBACK_COLORS);

  useEffect(() => {
    setColors(readColors());

    const target = document.documentElement;
    const observer = new MutationObserver(() => setColors(readColors()));
    observer.observe(target, { attributes: true, attributeFilter: ["data-theme"] });
    return () => observer.disconnect();
  }, []);

  const data: OverlapDatum[] = reports.map((report) => ({
    name: report.corpus_name ?? report.corpus_id,
    overlap: Number((report.overlap_score ?? 0) * 100)
  }));

  if (data.length === 0) {
    return (
      <div className="surface flex h-[280px] items-center justify-center rounded-sm p-4">
        <p className="ui-copy text-[14px]" style={{ color: colors.textDim }}>
          No overlap data yet.
        </p>
      </div>
    );
  }

  return (
    <div className="surface h-[280px] rounded-sm p-4 sm:h-[320px]">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -8 }} barCategoryGap="24%">
          <CartesianGrid stroke={colors.borderLight} strokeDasharray="2 4" vertical={false} />
          <XAxis
            dataKey="name"
            tick={{ fontSize: 11, fill: colors.textDim }}
            tickLine={false}
            axisLine={{ stroke: colors.border }}
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fontSize: 11, fill: colors.textDim }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(value: number) => `${value}%`}
            width={44}
          />
          <Tooltip
            cursor={{ fill: colors.borderLight, opacity: 0.4 }}
            content={<OverlapTooltip colors={colors} />}
          />
          <Bar dataKey="overlap" fill={colors.accent} radius={[3, 3, 0, 0]} maxBarSize={56} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
