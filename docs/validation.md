# Implementation validation

## Provenance and English-edition limits

The dated records below describe validation of the original upstream edition.
They are historical evidence, not claims that the English edition has been tested
natively in Lightroom or on another Mac. The English edition uses separate runtime
storage, keychain namespaces and port 8766. No original-edition user service or
credential is copied into this repository.

Raw benchmark JSON in `docs/benchmarks/` is intentionally preserved in its original
language, including Italian prompts and model responses. Translating a measured
response would alter the evidence. The English summaries below explain those
records without changing their results. Native English dialogs, current model
behavior and a clean installation on another Mac need their own tests.

## English edition — automated verification on November 19, 2026

The integrated English checkout passed 226 backend tests with one Apple Vision
helper test deselected, plus 62 frontend tests and a successful production build.
The general synthetic headless browser smoke passed, including the larger viewer,
keyboard navigation/focus, review, simulated rating workflow and mobile layout.
No real OpenAI analysis or native English Lightroom execution was performed by
these checks. The English API browser smoke also passed: three simulated requests and zero real
network calls, acknowledgement gating, cache reuse, empty-proposal manual review,
and no horizontal overflow at 390 pixels. Native English SDK dialogs and a clean installation
on another Mac remain unverified.

## Initial version 0.1.0 — historical

On the upstream Mac, 32 backend/API/Lua 5.1 simulation tests and 7 React tests passed.
TypeScript/Vite built and Python dependencies checked successfully. A real loopback
HTTP server with six synthetic previews verified compiled assets, cookie login,
import, conservative selection (five candidates for target three) and four eligible
rating-plan items. The temporary server was stopped afterward. Apple Vision was
compiled with Swift and run on a uniform synthetic image: zero faces, no error.
No personal photographs or direct Lightroom catalog database access were involved.

Coverage included idempotent import, duplicate filenames, virtual copies, revision
conflicts, immutable service presets, target/coverage behavior, manual decisions,
disk budgeting, resumption, token/origin guards, exclusive claims, journal-before-write,
rating/edit-time preservation, cancellation and receipts.

At that stage, Lightroom Classic 16.0 native testing was blocked by
`cgWindowNotFound`; Lightroom had not been opened. The authorized old test catalog
was separate from the unapproved primary catalog. In particular, `lastEditTime`
semantics after a manual zero → three → zero rating sequence remained unverified:
a simulated comparison cannot prove Adobe updates that field for such a sequence.
Catalog identity combines registered path and photo UUID/localIdentifier; replacing
a catalog at the same path with a copy retaining IDs is not automatically detected.
Do not reuse old services in that case; register the catalog again.

Flush/close and move journals protect process interruption, not hardware failure or
power loss before physical filesystem persistence. The initial baseline grouped
identical JPEGs only. Semantic models, people/scenes/eyes/poses and aesthetic scores
were uncalibrated; SigLIP had not yet been downloaded. Camera time offsets affected
chronological display, not equivalence. OpenAI analysis was not enabled at that
historical point; later sections supersede that status.

## Post-audit update — November 18, 2026

- 47 backend/simulated SDK tests passed, including 15 Lua tests; 13 React tests and
  TypeScript/Vite build passed.
- Regressions covered competing A/B plans, active-plan recovery after restart,
  exact confirmation, cancellation during write-gate wait, reused receipts,
  idempotent incremental import, catalog/identity conflicts, preserved baseline,
  decisions/target, persistent history, atomic replacement, version 1 manifest
  digest compatibility, archiving and reopening.
- Explicit local extraction and cache were tested with synthetic encoders/detectors:
  recovery, model-version invalidation and uncached detector failures. NumPy was
  installed for visual-neighbor tests; no model weights were downloaded for them.
- `scripts/browser_smoke.mjs` used headless Chrome and a real local HTTP backend
  with synthetic previews: decisions, undo/redo, local Apple Vision extraction,
  comparison/resolution, confirmed plan, claim, simulated SDK receipt, append,
  archive/reopen. No real ratings changed. Desktop 1500 px and mobile 390 px had
  no horizontal overflow.
- The pre-integration scale benchmark measured 1,000 records: about 16 ms for
  details and 0.087 s baseline; 5,000: about 63 ms and 1.002 s. All candidates were
  preserved. Only metadata and one synthetic preview per service were used; this
  was not a RAW, AI or thousands-of-thumbnails rendering benchmark.
- Finder still returned `cgWindowNotFound`; native `lastEditTime`, offline-original
  thumbnail availability, filtered candidate selection and SDK semantics remained
  untested. Optional collection creation/synchronization remained absent, with no
  calibrated real-sample semantic model and no OpenAI analysis calls.

Undo/redo affects manual decisions, not analysis or Lightroom stars. Serialization
tests cover normal plugin SDK operations and write-gate checks, not arbitrary
independent processes acting on the same catalog.

## Web dependency audit and initial visual revision

`npm audit --omit=dev` reported zero vulnerabilities. The complete audit identified
a development-tool picomatch ReDoS chain,
[GHSA-fc5q-39xc-vjpf](https://github.com/advisories/GHSA-fc5q-39xc-vjpf), with no fix
published in the source consulted on November 18, 2026. The suggested downgrade
was not applied automatically. The application serves static assets through Python;
Vite/Vitest/build globs accept no product user input and are not exposed as an app
service. Reassess the advisory before tool upgrades or exposing a development server.
A Starlette/httpx test-client deprecation warning did not cause test failure.

The initial single-page revision retained the main contact sheet, side tools, light
neutral palette and dark header. Quantity slider/number input synchronized; preview
size had a separate slider. Criteria details expanded and engine limits remained
visible. Seven React tests/build passed. Authorized headless screenshots used six
synthetic images; 1500 px desktop and 390 px mobile showed no horizontal overflow.

## First real SDK work — November 18, 2026

The owner opened an authorized test catalog and folder. Installation and connection
succeeded. The first import failed because `os.rename` is unavailable in Adobe’s
runtime; persistence switched to official file APIs with regression coverage.
Initial `cgWindowNotFound` entries describe earlier attempts; graphical control
subsequently worked partly, with dialog timeouts. Full round-trip/native rating
validation was still pending at this point; see `lightroom-test.md` for the protocol.

## Free text and presets — November 18, 2026

100 sandbox backend tests passed, with the synthetic Apple Vision test separately
passing outside the sandbox (101 total). Eighteen frontend tests, production build
and synthetic desktop/mobile browser smoke passed with no overflow at 390 px.

Qwen3-VL 4B MLX ran offline on 160 authorized previews using the original Italian
request for birds, no Wedding criteria and target seven: 70 yes, 62 no, 28 uncertain,
about 463 seconds before diversity reranking. These are model judgments, not manual
truth labels. SigLIP reranking took about seven seconds. The seven proposals were
visually inspected and showed ground/perched and flying birds. Global recall,
comparative quality, the uncertain images and situation coverage were not measured.

A negative request for elephants on two previews returned zero proposals and a
missing-match warning without forced filling. This did not prove absence across
all 160 photographs. The benchmark was separate from real service settings and
decisions, changed no stars, and can be reproduced with
`scripts/benchmark_instructions.py` on an authorized service. Complete reports and
images stayed in local application storage outside Git.

Hash/version cache and resumption tests covered exact original text in local and
OpenAI payloads, ambiguity, preferences, nonmatches and manual decisions. They do
not promise correct interpretation of arbitrary text. API key/model configuration
and payload building were then tested without network; native Keychain, transport,
budget/usage and real API testing were not yet complete.

## OpenAI workflow — November 18, 2026

Responses transport, estimates, persistent optional service budgeting, exact sample
consent, original text, cancellation/resumption, cache and receipts were implemented.
Earlier disabled/not-implemented notes were superseded. 118 backend tests passed,
excluding the unchanged previously checked Apple Vision helper. Fifteen tests covered
the API runner and three the model catalog. All transports were simulated; no real
photo transmission or API cost was incurred by these tests. Real Keychain/account
model discovery still required manual validation then.

Twenty-six frontend tests and production build passed. Read-only checks after
restart found a local model catalog, no API job on the real service, and zero API
usage/reserves. No real-account model-refresh request was run during this check.
The API browser smoke verified no transport during estimation, mandatory consent,
identical Unicode/whitespace, one assessment reused for two identical previews,
usage recording and reserve release. Desktop/mobile screenshots had no 390 px
overflow. The isolated fixture replaced transport before server startup and used
fake credentials, never OpenAI network access.

## Whole-sample selection revision — November 18, 2026

134 backend tests passed (Apple Vision excluded), 32 frontend tests, build and diff
check passed. Synthetic cases covered birds/portraits coverage, manual precedence,
old-cache invalidation, unified instructions/presets, stale warnings, direct API,
optional budget, global comparison, invalid ranking, reserves/cost, resumption,
rejected old plans and quantity recomposition without new calls.

Both browser smokes passed. API made three simulated requests: interpretation, one
assessment reused for two identical previews and global comparison. It preserved
original text and recomposed one → two candidates without calls. Screenshots were
inspected. Restart/read-only real-service checks showed no new API usage or reserve.
Real recognition and global-comparison quality still required the user’s manual test;
previous results were not automatically recomputed. New local logic required an
explicit analysis, and old API plans required a fresh estimate for global comparison.

## Incomplete local responses and scrolling — November 18, 2026

Read-only diagnosis found 150 invalid responses out of 160, eight nonmatches and
two matches; the old pipeline had incorrectly marked the proposal complete. One
category contained a literal prompt placeholder instead of requested subjects.
Without preserved raw outputs, exact causes of the invalid responses were unknown.

Local prompt v6 introduced a compact schema, 1,024-token limit, category validation
during repair and placeholder rejection. Cache version changed. At that historical
stage, incomplete responses blocked a new proposal, preserved decisions and marked
the old proposal stale; later uncertainty retention superseded that rule. Synthetic
tests did not prove model quality or justify fabricated matches.

All filtered cards became scrollable without Load more, with lazy preview loading.
140 backend tests (Apple Vision helper unavailable in sandbox), 34 frontend tests
and build passed. No new real inference or OpenAI request was made for this fix.

## Authorized local replacement: Qwen3.5-9B

The owner requested replacement despite the negative synthetic coverage result
recorded in `models.md`. MLX-VLM 0.4.3 and miniaudio 1.73 were installed and pip check
passed. Final-runtime offline loading was verified without inference. Atomic
configuration activated Qwen3.5-9B-MLX-4bit; restart confirmed instruction capability.
Only the provenance-checked prior 4B weights were removed: 3,109,734,493 bytes.
SigLIP remained separate. No service, decision, original or rating changed and no
OpenAI request occurred. 144 backend tests passed, one Apple Vision test excluded.

## Blocking before photo assessment — November 19, 2026

Read-only diagnosis: zero attempts/invalid responses, 160 unassessed photographs,
160 saved candidates. The 9B had invented generic ambiguity/unsupported limits for
a subject list; the pipeline had conflated blocked instructions with failed visuals.

Revision v9 added a conservative parser only for lowercase single-word category
lists without operators or extra criteria; other instructions still go through the
model. It preserved original text, distinguished collection alternatives from
same-photo co-occurrence, removed derived criteria from effective visual instructions
and removed unsolicited subject examples. Real contradictions/unverifiable requests
still block; inconsistent outputs are retried/rejected rather than fabricated yes.
Cache version changed. Failure reasons and partial/prior interpretations became
separate, saved candidates remained visible, and the old zero-invalid message was
normalized read-only without rewriting the service.

The actual model passed 11/11 synthetic-figure checks: 61.05 seconds, approximately
7.71 GB peak MLX. See [v9 raw report](benchmarks/local-model-9b-v9.json); failed v7/v8
attempts remain evidence. Reproduce with `scripts/check_local_model.py`. These
checks do not validate aesthetics or general instruction reliability. No new user
photo analysis, API request or star change occurred.

## Uncertainty retention and partial-result recovery — November 19

The last real attempt processed 160 images: 143 positive, 14 negative, one valid
uncertain and two invalid schema/category responses. The owner required uncertain
results to remain included rather than block the proposal.

`retain-uncertain-v1` first forms ordinary confirmed-category coverage, then retains
all uncertain/invalid/missing-preview/unassessed images unless manually excluded or
marked alternative. Needs-review images can exceed the target, do not prove coverage
and survive SigLIP reranking. Original assessments, valid cache and prompts/models
were not changed. Per-photo failures stopped aborting the whole local service;
blocking interpretation/global failures remained explicit. Acceptance preserves
review states and previous decisions; before acceptance the proposal stays separate.

A guarded recovery used 160 saved results to produce 15 ordinary plus three review
proposals, checking revision, original text/criteria, IDs and preview-hash metadata.
No inference, image read, API call, star write or embedding recomputation was needed.
It reused saved preference/scene ranking. The local proposal advanced revision
179 → 180 with 18 proposals, including three review items; decisions/stars stayed
unchanged. 172 backend tests (one Apple Vision excluded), 36 frontend tests and build
passed.

## HTTPS and unusable API photo responses — November 19

The macOS Python default SSL context had zero CA certificates. An unauthenticated
handshake to api.openai.com failed certificate verification, while certifi verified
TLS 1.3. Analysis/model discovery now explicitly use certifi with certificate and
hostname checks enabled. Fixed error messages expose neither provider bodies nor
secrets. No analysis was sent for the test. The exact old generic failure could not
be recovered; historical reserves remained and no automatic retry was started.

A real API attempt preserved 15 of 18 assessments before an unusable response.
The old ledger did not distinguish refusal, incomplete output and schema violation.
With verifiable usage, such photo outcomes now become uncertain and allow remaining
already-authorized calls to continue without retry. Uncertain photos stay in the
proposal unless manual exclusions prevail, without proving coverage. Network,
unverifiable usage, interpretation and global-comparison errors still suspend.
Receipts preserve safe diagnostic codes, not raw responses. The fix sent no new call.

## Guided Lightroom → web → Lightroom workflow — November 19

Five persistent phases, three routes, interrupted-sample resumption and current-only
outcome summaries were implemented. Web/Lua share an offline guide. Apply stars
is enabled only after the XMP attestation.

193 backend tests (Apple Vision helper unavailable), 48 frontend tests, TypeScript,
production build and guide/command consistency passed. Cases included local/hybrid/
direct routes, resumption/incompatibility, budget shortage, uncertain results,
changed criteria, restored phase, obsolete plan, zero changes, partial outcome and
keyboard focus. Both synthetic headless smokes passed comparison, decisions,
undo/redo, exact plan, simulated receipt, append/archive, presets, API consent,
cache reuse and 390 px overflow checks. Desktop style was visually inspected.

After an idle-state check, the upstream backend restarted. A read-only service check
showed Outcome, 10 candidates and a prior receipt for four applied stars; no new
analysis/application was performed. The user’s earlier successful manual round
trip does not validate new native guide/button dialogs, which still need manual
verification after reloading the plugin.

## API start, manual review and empty proposals — November 19

Successful API confirmation closes the summary and shows Analyze progress. A rejected
request keeps the dialog open with a reason. All-photo view shows selection membership
and Include/Exclude. Counts, filters and acceptance use automatic proposals with
manual overrides. An empty proposal shows all photos for explicit manual selection.

General quality/variety instructions are valid without mandatory subject categories.
Interpretation/global cache version changed, preserving photo-assessment keys.
True ambiguity becomes blocked rather than a completed empty analysis. Legacy
completed-zero-photo cases are recognized read-only. Explicit manual acceptance
allows Lightroom handoff without deleting blocked diagnostics.

200 backend tests (Apple Vision excluded), 53 frontend tests and build passed.
Read-only diagnosis of the reported case showed Configure, an explicit block,
a recoverable prior sample of nine and zero completed photo assessments. No new
real call or image mutation occurred; the revised real-case interpretation remained
for a user-confirmed test with simulated responses used in automation.

Both updated smokes passed automatic close/reopen, zero real sends, quantity changes
without calls, empty proposal with all six fixtures visible, manual include/exclude
with coverage confirmation and exact one-photo acceptance. No overflow at 390 px;
selected/unselected distinction was inspected visually.

## Navigable previews and extended API model catalog — November 19

Clicking a preview opens a larger viewer in the existing style. Arrow keys,
Previous/Next and Escape operate on the current filtered order, restoring focus to
the initial photo. Viewing/navigation makes no decisions; missing previews have a
clear message.

The API catalog distinguishes reviewed models, candidate families and incompatible
models. Unpriced candidates require separate payload consent, preserve saved budget
and record unknown monetary receipts as null/partial totals. Reasoning parameters
adapt by family; model selection never changes automatically and list refresh does
no inference.

205 backend tests (one Apple Vision helper excluded), 61 frontend tests and build
passed. Synthetic headless smoke covered navigation, Escape/focus, simulated star
flow and mobile layout. Only `/v1/models` was actually refreshed: the account exposed
GPT-6.2 Sol/Astra. New-model analysis responses were simulated; visual quality and
unreviewed-family compatibility require an explicitly confirmed real test.

After both services were idle, restart/read-only checks showed 44 available reviewed
or candidate identifiers including snapshots, Sol/Astra availability and the chosen
model still GPT-5.4 mini. Existing results/selections were unchanged.

## Distinct situations before variants — November 19

Shared selection preserves a representative for every distinct group before second
and third variants; targets remain soft. Synthetic cases verified 10 groups → 20
balanced images and 23 groups → 23 images for target 20, manual occupancy/exclusions,
categories and uncertainty. Local signatures/optional embeddings do not automatically
merge uniform backgrounds or tiny subjects. Complete-link grouping prevents chains.
API partitions must cover every matching index exactly once; individual caches
remain valid while only global comparison version changes.

222 backend tests (Apple Vision excluded), 62 frontend tests and build passed.
Both headless smokes passed with no real cloud calls or catalog access. Real-photo
group quality still needs manual verification; prior proposals do not recompute.
The public installation/use README and `scripts/install.command` were added.
Shell syntax, local links and installer sequence were checked with simulated commands;
a clean installation on another Mac was not performed. Pre-publication checks found
no real credentials, photos, catalogs or runtime databases in tracked files or the
examined history. These are historical upstream results, not a new English-edition
native or clean-install certification.

## 2026-11-19 — Virtualized contact sheet for 5,000 photos

The contact sheet and API picker use measured virtual rows, offscreen keyboard
focus and preserved expandable reasons. Selection, filters and viewer navigation
operate on the full list; no data migration is needed. All 68 frontend tests,
typecheck and build passed, as did both standard browser smokes with synthetic
fixtures and mocked API transport. The 5,000-record browser test passed scrolling,
filters, undo/redo, keyboard navigation, viewer, API picker and mobile layout:
20 initially mounted cards rather than 5,000, with no initial scroll jump.
See [performance.md](performance.md) for the reproducible comparison.
Production backend and Lua plugin are unchanged. No catalogs, original photos or
sidecars were accessed; no real cloud analysis ran. Safari and the owner's real
service still require manual verification.
