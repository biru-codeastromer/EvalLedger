"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { ContaminationReport } from "@/lib/types";

export function OverlapVisualizer({ reports }: { reports: ContaminationReport[] }) {
  const data = reports.map((report) => ({
    name: report.corpus_name ?? report.corpus_id,
    overlap: Number((report.overlap_score ?? 0) * 100)
  }));

  return (
    <div className="surface h-[280px] rounded-sm p-4">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <CartesianGrid stroke="var(--border-light)" vertical={false} />
          <XAxis dataKey="name" tick={{ fontSize: 11, fill: "var(--muted)" }} />
          <YAxis tick={{ fontSize: 11, fill: "var(--muted)" }} unit="%" />
          <Tooltip />
          <Bar dataKey="overlap" fill="var(--text)" radius={[2, 2, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

