import { ContaminationStatus } from "@/lib/types";

const STATUS_STYLES: Record<ContaminationStatus, { color: string; background: string }> = {
  clean: { color: "var(--status-clean)", background: "var(--status-clean-bg)" },
  flagged: { color: "var(--status-flagged)", background: "var(--status-flagged-bg)" },
  contaminated: {
    color: "var(--status-contaminated)",
    background: "var(--status-contaminated-bg)"
  },
  pending: { color: "var(--status-pending)", background: "var(--status-pending-bg)" },
  unchecked: { color: "var(--status-pending)", background: "var(--status-pending-bg)" }
};

export function StatusPill({ status }: { status: ContaminationStatus }) {
  const style = STATUS_STYLES[status];

  return (
    <span
      className="inline-flex rounded-[2px] px-2 py-1 font-[var(--font-mono)] text-[10px] uppercase tracking-[0.12em]"
      style={{ color: style.color, background: style.background }}
    >
      {status}
    </span>
  );
}

