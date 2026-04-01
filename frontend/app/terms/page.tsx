export default function TermsPage() {
  return (
    <div className="section-space">
      <div className="page-frame max-w-[760px]">
        <div className="mono mb-4">Draft policy</div>
        <h1 className="display-lg mb-8">Terms of Service</h1>
        <div className="prose-rfc text-[16px] leading-[1.85] text-[var(--text-dim)]">
          <p>
            These draft terms describe the baseline conditions for using EvalLedger. They are
            product-complete for implementation work, but they should receive legal review before a
            public production launch.
          </p>
          <p>
            By creating an account, submitting a benchmark, or using the API or CLI, you represent
            that you have the authority to provide the material you upload and that doing so does
            not violate another party&apos;s rights, confidentiality obligations, or applicable law.
          </p>
          <p>
            You remain responsible for the content of benchmark artifacts, metadata, citations, and
            any downstream use of materials you submit. EvalLedger may preserve audit history around
            submissions and administrative actions to maintain provenance and registry integrity.
          </p>
          <p>
            EvalLedger may suspend or remove content that is unlawful, misleading, abusive, or
            materially harmful to the operation of the registry. We may also temporarily disable
            submissions, access tokens, or benchmark records during incident response or abuse
            investigation.
          </p>
          <p>
            The service is provided on an as-is basis. Before launch, warranty disclaimers,
            limitation-of-liability language, governing law, dispute-resolution terms, and export
            control language should be reviewed and finalized with counsel.
          </p>
          <p>
            Continued use after future policy updates may constitute acceptance of those updates
            once a formal notice and revision process is in place.
          </p>
        </div>
      </div>
    </div>
  );
}
