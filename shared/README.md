# Version 1 exchange contract

The executable contracts are defined in `backend/lrc_selection/models.py`.
OpenAPI is served by the backend. Plugin exchanges use `schema_version: 1`.

- `POST /api/imports`: full service manifest; identical retries are idempotent.
- `PUT /api/services/{id}/photos/{photo_id}/preview`: JPEG body; Bearer authentication.
- `POST /api/services/{id}/complete`: finish an import.
- `GET /api/services` and `GET /api/services/{id}`: summaries and current state.
- `PUT /api/services/{id}/settings`: expected revision and settings snapshot.
- `PATCH /api/services/{id}/decisions/{photo_id}`: revision, state and lock;
  explicit `confirm_last` for the last candidate.
- `POST /api/services/{id}/analyze`: explicit analysis start with expected revision.
- `POST /api/services/{id}/rating-plan`: prepare a reviewable list; applies no stars.
- `POST /api/services/{id}/rating-plan/confirm`: `{batch_id}` confirms the exact list
  reviewed by the user.
- `GET /api/services/{id}/rating-plan/latest`: return the active plan, otherwise the
  confirmed plan; never an arbitrary newest plan. Obsolete plans are rejected.
- `POST /api/services/{id}/rating-plan/claim`: reserve the plan and block web changes
  until a complete receipt arrives.
- `POST /api/services/{id}/rating-receipts`: per-plan outcomes; identical retries are
  idempotent.

Only `target_rating: 1` from baseline zero is produced by the planner. The plugin
must validate every item again rather than trust the client. Photo identity uses
IDs, never filenames. Receipts contain no originals, catalogs or secrets.

## Additive version 1 extensions

- `POST /api/services/{id}/append`: `{schema_version:1,id:<operation UUID>,catalog_id,
  photos:[Photo]}` returns `{photo_ids,completed}`. The catalog must match; identical
  retries are idempotent and identity conflicts are rejected. Existing photos are
  ignored without updating baselines.
- `POST /api/services/{id}/complete`: additions require `{import_id}`; the initial
  import retains an optional body. Additions invalidate plans and require explicit
  analysis; the target is preserved.
- `PUT /api/services/{id}/archive`: `{revision,archived}`. Only completed operations
  can be archived; data is not deleted.
- `POST /api/services/{id}/replace`: `{revision,from_photo_id,to_photo_id}`. Atomic
  replacement of an unlocked candidate and alternative in the same group.
- `POST /api/services/{id}/undo` and `/redo`: `{revision}`. Persistent decision
  history; service details expose `can_undo` and `can_redo`. Does not undo Lightroom
  changes.
- `GET /api/capabilities`: local component availability (`features`, `faces`,
  `siglip`) without private paths.
- `POST /api/services/{id}/features`: `{revision}`, explicit extraction using
  configured local components. Uses the same job state; no download or cloud request.

Update the backend, web app and plugin together. New plugins require explicit plan
confirmation. `PRAGMA user_version=1` applies only to the application SQLite store;
updates are additive and do not rewrite existing services. Missing archive/history
fields use initial defaults. Existing version 1 manifest digests are preserved.

## Guided navigation version 1

`GET /api/services/{id}` adds `workflow` with `schema_version:1`, route
`local|hybrid|openai`, phase `configure|analyze|review|lightroom|outcome`, proposal
state, counts and plan identifiers. `outcome` is populated only for the receipt
relevant to the current revision and separates `applied`, `skipped`, `conflict`,
`uncertain` and `total`. It does not authorize actions.

`Settings.workflow_path` is optional; absent values use the previous `mode`.
Direct OpenAI retains `mode=hybrid` for compatibility with existing guards, while
navigation distinguishes it explicitly.

`GET /api/services/{id}/api-status` adds `resume` for the latest interrupted attempt:
plan, exact sample IDs, compatibility, reason, progress and final target. A new
estimate does not hide the interrupted attempt. This summary never restores
consent or starts API calls.

The proposal exposes `effective_shortlist`: the automatic list with manual
inclusions and exclusions applied. The workflow summary includes `blocked` and
`blocked_reasons`; an interpretation block is not completed photo analysis.
Confirming a manual selection can clear the operational block without removing
its diagnostics.
