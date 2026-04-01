export default function PrivacyPage() {
  return (
    <div className="section-space">
      <div className="page-frame max-w-[760px]">
        <div className="mono mb-4">Draft policy</div>
        <h1 className="display-lg mb-8">Privacy</h1>
        <div className="prose-rfc text-[16px] leading-[1.85] text-[var(--text-dim)]">
          <p>
            This page describes how EvalLedger handles account information, benchmark metadata,
            uploaded artifacts, and operational logs. It is a working product policy intended to be
            reviewed by counsel before a public launch.
          </p>
          <p>
            EvalLedger stores the account details you provide at registration, including your email
            address, username, optional profile fields, API keys, and benchmark ownership metadata.
            We also store audit records tied to submission, verification, and account-management
            actions so registry changes remain attributable.
          </p>
          <p>
            When you upload a benchmark artifact, EvalLedger stores the artifact itself, the
            metadata needed to describe it, and derived integrity information such as SHA-256
            digests, file size, and contamination-analysis outputs. Uploaded benchmark material may
            contain sensitive research content, so artifacts should only be submitted by users with
            the right to share and process them.
          </p>
          <p>
            EvalLedger records structured application logs, health checks, request identifiers, and
            operational error events to keep the system reliable and auditable. We use those records
            to debug incidents, review abuse reports, and understand how the service is performing.
          </p>
          <p>
            We do not promise permanent retention for every artifact or log entry in this draft
            policy. Before production launch, retention windows, deletion handling, subprocessors,
            and jurisdiction-specific rights should be reviewed and finalized.
          </p>
          <p>
            If you need a benchmark removed or corrected before the final privacy program is in
            place, contact the maintainers directly and include the benchmark slug or EvalLedger
            identifier involved.
          </p>
        </div>
      </div>
    </div>
  );
}
