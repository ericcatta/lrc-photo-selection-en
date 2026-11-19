# Architecture and safety

## Components and isolation

The official Lua SDK plugin reads only explicitly selected photos, requests JPEG
previews and sends a version 1 JSON manifest to FastAPI on `127.0.0.1:8766`.
React/TypeScript is compiled and served by that backend. SQLite belongs exclusively
to the application; the Lightroom catalog database is never opened directly.

English runtime data lives under `~/Library/Application Support/LrC Photo Selection EN/`
with private permissions. The plugin uses the SDK keychain and separate
`lrc-photo-selection-plugin-en` storage for registrations and journals, outside the
catalog. Its toolkit identifier is `com.ericcatta.lrc-photo-selection-en`. The local
connection token is separate from any OpenAI key. Plugin requests use Bearer
authentication; browser access uses an HttpOnly, SameSite Strict cookie. Host and
Origin are checked, permissive CORS is absent, HTTP access logging is disabled and
there is no telemetry. English storage and credentials do not reuse Italian data.

## Identity and revisions

Each service has a UUID, a catalog ID registered in plugin-local files, photo UUIDs
and SDK `localIdentifier` values. Filenames are not keys. Virtual copies keep their
own identity. Copied or moved catalogs are not automatically relinked. Web mutations
require an expected revision; retransmitted manifests are idempotent only when the
entire payload matches.

Import has separate manifest, preview and completion stages. Preview filenames are
derived from ID hashes; original paths are never used as write destinations. The
backend validates JPEGs and does not open originals. Preview failures are visible
and never count as evidence of equivalence.

## Data separation

Services separate immutable imported facts (`photos`), settings and preset snapshots,
versioned automatic proposals, manual decisions, jobs and plugin receipts. SQLite
transactions serialize edits and plan preparation. Analysis results are discarded
if the service revision changed. Interruptions preserve resumable state and decisions.

Incremental imports have their own operation ID and complete using that same ID.
Only new photographs are added; existing facts and decisions are not replaced.
Older proposals remain available as stale, new photographs begin as candidates,
and explicit analysis is required before preparing stars.

Decision history stores before/after values for single decisions or atomic
replacements with a persistent cursor. Editing after Undo starts a new branch and
discards the old redo branch. This is not analysis history: undoing an override can
leave the visible outcome unchanged when the automatic proposal independently
chooses it. History operations never modify Lightroom. Archiving is local and
reversible; previews and originals are not deleted.

## Star ratings

The backend prepares an immutable plan, explicitly confirmed in the web app. Only
the plugin executes it through the SDK. Resumption retrieves the active plan even
when newer plans exist. The SDK dialog shows identifiers, filenames and exact
operations. Preconditions include baseline zero, known edit time, matching identity
and catalog, no previous attempt and a fresh comparison inside the catalog write
gate. Existing ratings, later edits and ambiguous cases are skipped. The local
journal protects interruptions between a rating change and its receipt. Excluding
a candidate later never automatically removes stars.

No verified public SDK getter is available for automatic XMP writing. Before each
application, the user must check that automatic metadata writing is disabled in
Lightroom settings, then attest that check in the plugin. Stars remain blocked if
that state cannot be verified. The plugin never changes preferences or invokes
metadata saving; the checkbox is a manual precondition, not automatic verification.

## Text, presets and local models

A preset is optional. Selecting one copies instructions into editable service
settings; updating or saving a preset leaves earlier service snapshots unchanged.
The original text is preserved in full for each visual assessment. Internal derived
context never replaces it or adds an interpretation-confirmation step for the user.

The initial baseline grouped only byte-identical derived JPEGs; even those do not
prove equivalence of high-resolution originals. The historical Qwen3-VL 4B adapter
was replaced by Qwen3.5-9B MLX 4-bit with MLX-VLM 0.4.3; see `models.md` for pinned
revisions and the sequence of decisions. Loading during analysis is offline. Free
text analysis is blocked if the required local model is unavailable.

Each preview receives a structured yes/no/uncertain assessment, a reason, ordinal
preferences and tentative scene descriptors. Ambiguous or unverifiable criteria
remain visible and do not count as satisfied. Uncertain, unavailable or unusable
assessments remain included as Needs review beyond the ordinary proposal, even
above the target, except where manual exclusions prevail. They do not prove
matching content or coverage; unrelated images do not fill a target automatically.
Models do not certify identity, equivalence or complete coverage.

The shortlist is a review proposal distinct from conservative current candidates.
Confirm selection records reversible service decisions without changing Lightroom.
Existing manual decisions prevail; the star plan is a separate zero-to-one step.
Local detail extraction uses separate caches keyed by component identity, preview
checksum and version. See `audit-plan.md` for the evidence protocol and limits.

## OpenAI

Configuration stores the API key in the native keychain. Responses payloads keep
the exact original text in a user message separate from technical instructions and
set `store:false`. Saving configuration sends no photographs. Transport is enabled
only by an estimated, explicitly confirmed plan. The application ledger
`api-jobs.sqlite3` holds immutable plans, reserves, usage and cache entries.
Recovery after interruption happens only after acquiring the server lock and sends
no requests. Dynamic account availability is separate from verified capabilities
and pricing. See `openai.md`.

## Situations first, then variants

`selection.py` centralizes category coverage, manual precedence, a representative
for every eligible distinct group and balanced additional alternatives. The target
does not truncate the first round. Later rounds prefer less represented groups,
counting manual inclusions already present. Ranking chooses photographic merit
inside a group. A mixed 70/30 score is no longer used to sacrifice a distinct
situation for a stronger duplicate.

Local grouping uses conservative signatures of derived previews: framing,
structure and color, plus embedding agreement when available. All members must be
mutually similar so similarity chains cannot merge separate situations. Missing or
insufficient evidence stays separate; scene descriptions alone do not prove
equivalence. OpenAI returns a reasoned partition of matching results from the
confirmed global comparison, validated by the backend. Both remain reviewable
interpretations, not statements of personal identity or original-file equivalence.

Test exclusions apply to team operations, not product catalog-name or year rules.
