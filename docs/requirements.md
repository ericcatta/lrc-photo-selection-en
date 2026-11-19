# Requirements and decisions

A personal application for the first selection of photographic services. The initial
preset is Wedding; quantity and criteria are chosen before starting selection.
The target is between one and the imported count, never a hard cap. Preserve
coverage above it. Manual decisions can make it infeasible: report that rather than
reversing those decisions. Eligible evidence is required; do not invent matches.

## Constraints

The only allowed Lightroom mutation is a star rating. No collections, plugin
metadata, flags or labels are written. Originals, develop settings and sidecars
remain untouched. Use the official SDK, never SQL access to the catalog. Temporary
previews are separate. Applying stars requires explicit review and verification
that automatic metadata writing is disabled.

## Workflow

Lightroom selection → title → previews and catalog/photo/virtual-copy identity →
local service → criteria and quantity → explicit analysis → candidates and
alternatives → manual review → rating preview → SDK application and receipt.
Importing does not start analysis. The English edition has separate storage,
credentials, toolkit identity and backend port 8766; Italian data is not migrated.

## Coverage

Distinguish moment, scene, person composition, pose/action and burst. Isolated
photos, unique imperfect moments, changed people, laughter versus serious poses
and uncertain detections must not be discarded solely for technical quality.
Alternatives keep a representative, evidence and a recovery path. Detected groups
do not imply all real situations were recognized.

## Configuration and data

Presets are editable and creatable, with versioned service snapshots. Current
preset settings do not alter earlier services. Free-form instructions retain
visible supported/ambiguous/unsupported states. Camera offsets apply only within
the app. Local analysis is offline after setup; optional cloud analysis is explicit.

Separate imported metadata, model interpretations/versions, rules/presets,
automatic proposals, manual decisions and rating receipts. Manual locks prevail
over new analysis. Resumption and revisions persist. Do not invent reasons.
Synthetic fixtures are clearly isolated from real services.

## API

Transmit only explicitly confirmed previews. Face observations are local, without
identity claims. Store the key in Keychain, never frontend/Git/logs. Provide an
estimate and optional per-service budget, accounting for requests already started,
limited concurrency, cache and conservative interruption/resumption. Do not buy
credits or enable automatic top-ups. Claimed account credits are not a verified
balance; terms and prices require verification during configuration.

## Acceptance

Prioritize missed meaningful situations, incorrectly merged compositions, unique
images excluded and manual decisions violated. Only then optimize duplicates,
time and cost. The first milestone is the full manual round trip, followed by local
validation on an agreed real sample and an explicitly authorized cloud test.
No user photographs may be inspected before the sample is identified.

## Distinct situations and variants — November 19, 2026

Both local and OpenAI selection first retain a representative from every eligible
distinct situation group. Photographic merit chooses the best representative
within that group; a stronger near-duplicate must not replace another situation.
This is the default even when the instructions do not mention variety.

The target remains soft: 23 situations can produce 23 candidates for a target of
20. For 10 situations and a target of 20, distribute second choices across groups,
then third choices, until reaching the target or exhausting eligible alternatives.
Skip groups without further variants. Manual inclusions remain and count toward
group occupancy; manual exclusions and alternatives are not automatically restored.
Uncertain images stay marked Needs review and do not become evidence of coverage.

Similarity is provisional evidence, not certified identity. A common category such
as birds is insufficient to treat photographs as interchangeable. The OpenAI
comparison covers only the confirmed sample, not every imported photograph.
Samples are never enlarged and new requests never sent automatically.
