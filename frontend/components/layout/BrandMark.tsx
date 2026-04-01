export function BrandMark({
  className = "h-8 w-8",
  title = "EvalLedger mark"
}: {
  className?: string;
  title?: string;
}) {
  return (
    <svg
      viewBox="0 0 64 64"
      role="img"
      aria-label={title}
      className={className}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <rect x="6" y="6" width="52" height="52" rx="14" fill="var(--surface)" stroke="var(--text)" strokeWidth="3" />
      <path d="M22 18V46" stroke="var(--text)" strokeWidth="3" strokeLinecap="round" />
      <path d="M18 22H46" stroke="var(--text)" strokeWidth="3" strokeLinecap="round" />
      <path d="M18 32H46" stroke="var(--text)" strokeWidth="3" strokeLinecap="round" />
      <path d="M18 42H40" stroke="var(--text)" strokeWidth="3" strokeLinecap="round" />
      <circle cx="44" cy="42" r="6" fill="var(--text)" />
      <circle cx="44" cy="20" r="5" fill="var(--surface-2)" stroke="var(--text)" strokeWidth="3" />
    </svg>
  );
}
