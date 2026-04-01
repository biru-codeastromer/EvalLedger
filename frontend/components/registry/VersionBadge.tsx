export function VersionBadge({ version }: { version: string }) {
  return (
    <span className="font-[var(--font-mono)] text-[11px] uppercase tracking-[0.12em] text-[var(--muted)]">
      {version}
    </span>
  );
}

