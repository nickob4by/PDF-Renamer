# CONTEXT.md — domain glossary

Terms used across this codebase. Keep names consistent in code, docs, and
architecture reviews.

- **Receipt page** — a single page of an input PDF, produced by `splitter`.
  Every page is processed independently by the pipeline.
- **Candidate** — one OCR-extracted row (company text + amount) that might
  identify a company. Produced by `extractor` from OCR words.
- **Verdict** — the outcome of running one receipt page through the pipeline:
  matched company, confidence, billing period, and would-be filename, or a
  failure reason. Produced by `page_verdict.PageVerdict`. Side-effect free:
  it never writes to Output/Failed.
- **Billing number** — the numeric suffix of a billing reference (e.g.
  `0055978`), optionally carrying a trailing `S` marker that is stripped.
- **Billing period** — the period code (e.g. `0426`) resolved from a billing
  number via `billing_periods.txt`.
- **Master record** — one row of `master.xlsx`: STL ID, company name, billing
  number, net amount. The billing number may be a full reference string
  (e.g. `TS-WFP-227F73-0000086`) or a digit-style suffix.
