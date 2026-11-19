# lrc-photo-selection-en

## Non-negotiable safety

- Access Lightroom exclusively through the official Lua SDK. Never read or write
  its catalog database directly.
- The only allowed Lightroom mutation is a photo’s star rating after explicit
  preview and confirmation. No collections, flags, labels, keywords, plugin
  metadata or develop changes.
- Never delete, move, rename, overwrite or modify original photographs or sidecars.
  Temporary previews and crops live only in application storage.
- Do not apply ratings while automatic metadata writing is enabled or unverified.
  Never change Lightroom preferences automatically or invoke `saveMetadata`.
- Preserve existing ratings and later manual decisions. Repeated imports must not
  overwrite later manual work.
- Do not inspect user photos until a sample is explicitly identified. Do not make
  cloud analysis requests without explicit sample and cost authorization.
- No online hosting, telemetry, model downloads during import, or secrets/photos/
  catalogs in Git.

## English edition and product

English UI and documentation. Keep this edition isolated: runtime folder
`~/Library/Application Support/LrC Photo Selection EN`, backend port 8766, unique
plugin toolkit and keychain namespaces. Do not read, migrate or modify Italian
runtime data or credentials.

Coverage precedes reduction. Every photo begins as a candidate. Alternatives keep
representatives and evidence; uncertain results preserve candidates. The requested
quantity is a minimum/target, not a hard cap. Preserve one eligible representative
per distinct situation before balanced additional variants. Manual decisions
prevail; report infeasibility rather than reversing them. Presets are versioned
snapshots per service. Unsupported free-form criteria remain visible.

## Development

Python/FastAPI/SQLite backend, React/TypeScript frontend and official Lua SDK plugin.
Store runtime data outside the repository in Application Support. Separate imported
facts, interpretations, settings, proposals, decisions and rating receipts. Version
public exchanges. Clearly label synthetic fixtures and never mix them with real
services. Test behavior and safety invariants; distinguish implementation from
actual validation.

## Owner orchestration preferences

Use Astra Medium as orchestrator when available. Personal agents: planner
`gpt-6.1-sol` medium; grunt `gpt-6-luna` low; helper `gpt-6-luna` low. Delegate useful
independent work with clear ownership and avoid redundant investigation. Explain
unavailable configured models before substitution. The owner subsequently authorized
choosing the lightest available capable model, including the available
`gpt-6.1-sol` grunt.

## Test authorization and workflow decisions

- Use only explicitly authorized test catalogs/samples or synthetic fixtures.
  Never open the unapproved primary catalog. Do not add product rules blocking
  catalog years. Open Lightroom from the chosen catalog file, not generic startup.
- Prior upstream real-sample authorization does not authorize new English-edition
  analysis or writes. The user runs real tests manually; do not start analysis or
  cloud transmission on their behalf.
- Temporary candidate selection through the SDK is allowed; it writes no metadata,
  collection or file. Optional Classic collection creation is not implemented and
  requires separate native synchronization testing.
- Services and archiving stay local; additions require the same catalog and preserve
  imported baselines and decisions.
- Confirm star plans in the web app and again in the plugin. Resume the active plan,
  never an arbitrary newest plan. Require the XMP check before applying stars.
- Browser tests use synthetic fixtures only. Headless Chrome was authorized. Native
  control has historically returned `cgWindowNotFound` or dialog timeouts; do not
  treat simulations as native SDK validation.
- Selecting a preset fills a single editable instructions field. Updating or saving
  a preset is explicit; previous snapshots remain immutable. Legacy criteria are
  merged visibly and only consolidated by explicit save.
- Preserve original text exactly, including for APIs; technical context never
  replaces it. No interpretation confirmation step is required. Report meaningful
  ambiguity, conflict, missing matches and actual limits.
- Local analysis before OpenAI is optional. Estimates require no mandatory overall
  budget; explicit confirmation authorizes the displayed per-send guard. A cumulative
  budget is optional. Unknown pricing requires distinct explicit consent.
- Final API quantity is separate from local quantity and can be recomposed from
  retained results without new sends. Original instructions and the whole confirmed
  sample govern selection; technical sharpness does not erase meaningful categories.

## Historical evidence

Benchmark JSON files are raw upstream evidence and may contain original Italian
prompts and responses. Preserve their contents and label their provenance; do not
translate measured outputs or imply English-edition validation from those records.
