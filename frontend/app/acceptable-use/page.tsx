export default function AcceptableUsePage() {
  return (
    <div className="section-space">
      <div className="page-frame max-w-[760px]">
        <div className="mono mb-4">Draft policy</div>
        <h1 className="display-lg mb-8">Acceptable Use</h1>
        <div className="prose-rfc text-[16px] leading-[1.85] text-[var(--text-dim)]">
          <p>
            EvalLedger is built to support legitimate benchmark registration, provenance tracking,
            and contamination analysis. Use of the service should preserve the integrity of those
            goals.
          </p>
          <p>
            You may not use EvalLedger to upload malicious files, exfiltrate data, impersonate
            another researcher or institution, interfere with submission workflows, or overwhelm the
            service with automated traffic outside approved testing or operational use.
          </p>
          <p>
            You may not submit artifacts that you do not have the right to process, artifacts that
            intentionally hide their contents, or metadata designed to mislead other users about a
            benchmark&apos;s origin, version history, or contamination status.
          </p>
          <p>
            Reverse engineering, scraping, or automation for legitimate research, interoperability,
            or reproducibility purposes should remain measured, attributable, and consistent with any
            published rate or access controls.
          </p>
          <p>
            EvalLedger may remove content, revoke credentials, or block access when activity puts
            benchmark records, user data, or platform availability at risk. This draft should still
            be reviewed alongside final moderation and trust-and-safety policy decisions.
          </p>
        </div>
      </div>
    </div>
  );
}
