# Audit and implementation — November 2026

## Approved delivery order

1. Immutable confirmed star plans, active-plan resumption, cancellation inside the
   write gate and persistent receipts; unsupported criteria and revisions remain clear.
2. Real testing only on the explicitly authorized test catalog. Missing graphical
   control never authorizes generic Lightroom startup or direct catalog database access.
3. Incremental services in the same catalog, local archiving, reversible decisions,
   comparison and keyboard shortcuts.
4. Local evidence and face crops; calibrate similarity on an authorized real sample
   before using it to reduce candidates.
5. Optional local Classic collections only after real SDK tests and proof that
   creation does not enable synchronization. No collection writes are implemented.

Synthetic work can proceed while native testing is blocked. This does not count
as passing a Lightroom test. English native dialogs require their own manual test.

## Product references

- Narrative: face close-ups alongside the full photograph preserve context.
  https://help.narrative.so/en/articles/7337371-zoom-and-close-ups-in-narrative
- Aftershoot: assisted group/duplicate review with manual selection.
  https://support.aftershoot.com/en/articles/5223473-get-started-with-aftershoot-culling
- Adobe Assisted Culling: inspectable criteria and results.
  https://helpx.adobe.com/lightroom-classic/desktop/organize-photos-in-lightroom-classic/assisted-culling.html
- Classic collection synchronization is a separate option. This product fact alone
  does not establish SDK behavior.
  https://helpx.adobe.com/uk/lightroom-classic/desktop/organize-photos-in-lightroom-classic/photo-collections.html

Develop changes, deletion, flags and quality-only exclusion automation are not adopted.

## Local evidence

Extraction reads only imported previews. `feature-cache.sqlite3` in application
storage contains successful results indexed by preview SHA-256 and component
identity. SigLIP identity includes weights/configuration and runtime; Apple Vision
identity includes executable hash and OS version. Interruption preserves written
cache entries; detector errors are not stored as valid evidence. Combined results
apply only to the checked service revision.

Visual neighbors are comparison suggestions rather than automatic equivalence or
exclusion claims. No threshold is declared calibrated. Face crops use normalized
Apple Vision coordinates with a bottom-left origin; they do not establish identity,
complete person detection or reliable eye assessments.

## Reproducible synthetic benchmark

Run `.venv/bin/python scripts/benchmark_scale.py`. It creates two isolated temporary
directories, imports 1,000 and 5,000 synthetic metadata records with one uniform
preview per service, measures detail reads and preview requests, then runs the
conservative engine. Missing-preview photographs must remain candidates. It does
not measure thousands of JPEG imports, browser thumbnail rendering, AI accuracy
or RAW performance.

The human benchmark remains `scripts/benchmark.py`: annotate meaningful situations,
unique images and pairs that must not be grouped. Keep calibration separate from
verification. Personal photographs and identifying annotations do not belong in Git.
