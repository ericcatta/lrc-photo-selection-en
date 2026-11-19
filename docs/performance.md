# Contact-sheet performance with 5,000 photos

The browser keeps only visible rows and nearby rows mounted. The complete list
remains available for filters, counts, manual decisions, comparison and the
navigable preview. Measured rows preserve the responsive grid and expandable
reasons; keyboard focus can reach a photo that has not been rendered yet.
There are no pages or “load more” buttons.

The OpenAI sample picker is virtualized too. Checkbox selection is independent
of mounted rows; the estimate’s exact list is rendered only when expanded.
Scrolling and filtering never start an analysis. HTTP caching and authentication
protections are unchanged.

## Reproducible verification

After installing development dependencies and building the frontend:

```sh
PYTHONPATH=backend node scripts/scale_browser_smoke.mjs --english
```

Requires Google Chrome at its standard macOS location. The test starts an
isolated backend on port 18767 with 5,000 synthetic records and a single generated
shape image linked to those records. It never accesses real photos, catalogs or
credentials, and performs no cloud analysis. `LRC_SMOKE_WEB_DIR` can point to a
staged build without replacing the installed interface.

The initial comparison used the Italian edition on the same Mac with headless
Chrome at 1500 × 1100; both editions share the virtualization component:

| Measurement | Before | After |
| --- | ---: | ---: |
| Initially mounted cards | 5,000 | 20 |
| DOM elements | 140,133 | 727 |
| Initial render | 1,135 ms | 223 ms |
| Exclude with coverage confirmation | 1,672 ms | 219 ms |

These are indicative synthetic measurements, not timing guarantees for other
Macs or Safari. The test also checks undo/redo, filtering, bottom scrolling,
resizing, keyboard navigation across unmounted rows, the viewer, 390 px mobile
layout and preserved decisions. The API picker checks selection and deselection
without transmission. No changes to the production backend, Lua plugin,
catalogs, original photos or sidecars are required.
