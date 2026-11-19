# Offline Lightroom guide

The canonical content is `docs/workflow-guide.json`. After editing it, run
`python3 scripts/generate_workflow_guide.py`; `--check` verifies that the Lua and
web copies are current. Do not edit `GuideData.lua` or `web/src/guide-data.json`
manually.

The menu item **Guide — from Lightroom to selection and back** and the Guide
buttons in Prepare service and Apply stars use only the official SDK for views.
The guide requires no backend, connection, token or active catalog.

Star application binds `actionBinding.enabled` to the XMP confirmation checkbox.
A defensive check also returns a clear message without claiming the plan or
applying stars. Changes remain blocked until the user confirms the XMP check.
The plugin never changes Lightroom preferences.

The English edition is isolated from the Italian edition:

- Toolkit identifier: `com.ericcatta.lrc-photo-selection-en`.
- Plugin storage: `lrc-photo-selection-plugin-en` under SDK application storage.
- Local backend: `http://127.0.0.1:8766`.
- Backend data: `~/Library/Application Support/LrC Photo Selection EN`.
- Local connection key: `loopback-token-en`, in the English plugin namespace.

Automated checks use Lua 5.1 simulations for the offline guide, generated content,
actual menu command names, XMP gating, and complete/partial outcomes. Native
rendering and button binding must be tested manually after **Reload Plug-in** in
Lightroom; simulations do not replace that check.

SDK reference: `LrDialogs.presentModalDialog`, `actionBinding` and
`viewFactory:push_button` in the Adobe Lightroom SDK
([reference mirror](https://lrc.mcor.dev/modules/LrDialogs.html)).
