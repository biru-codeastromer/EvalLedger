import { AuditEvent } from "@/lib/types";

function formatAction(action: string): string {
  return action.replaceAll(".", " ");
}

export function ActivityFeed({ events, emptyMessage }: { events: AuditEvent[]; emptyMessage: string }) {
  if (events.length === 0) {
    return <p className="text-[15px] text-[var(--text-dim)]">{emptyMessage}</p>;
  }

  return (
    <div className="space-y-3">
      {events.map((event) => (
        <div
          key={event.id}
          className="rounded-sm border p-4"
          style={{ borderColor: "var(--border)", background: "var(--bg)" }}
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="mono">{formatAction(event.action)}</div>
            <div className="text-[13px] text-[var(--muted)]">
              {new Date(event.created_at).toLocaleString()}
            </div>
          </div>
          <p className="mt-2 text-[15px] text-[var(--text-dim)]">
            {event.summary ?? "Recorded activity in the EvalLedger audit trail."}
          </p>
          <div className="mt-2 text-[13px] text-[var(--muted)]">
            {event.actor ? `By ${event.actor.username}` : "Recorded by the system"}
            {event.resource_slug ? ` · ${event.resource_slug}` : ""}
          </div>
        </div>
      ))}
    </div>
  );
}
