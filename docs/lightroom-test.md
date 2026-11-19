# Lightroom Classic manual test

Use only a catalog and small sample explicitly authorized by the owner. Open the
chosen test catalog directly; do not launch Lightroom on an unknown last-used
catalog. The English edition must not use the Italian edition’s storage or tokens.
The plugin does not impose catalog-name or year restrictions in the product.

1. In **File → Plug-in Manager**, add `plugin/lrc-photo-selection.lrplugin`.
   Confirm that **Photo Selection (English)** is selected. Reload it after code changes.
2. Start the English local backend on port **8766**. In **Library → Plug-in Extras →
   Configure local connection**, confirm the token from the English backend data folder.
3. Select the agreed sample and use **Prepare service**. Compare preview counts and
   identifiers, including a virtual copy when available. If originals are offline,
   preview availability depends on the SDK thumbnail response; do not locate or
   reconnect originals. Resume an interrupted import using the same selection.
4. Record the initial ratings, develop settings, flags and collections. When
   authorized and available, record checksums of originals and sidecars. In the web
   app, test review, comparison, include/exclude, locking, and the exact star plan.
5. In **Catalog Settings → Metadata**, verify that **Automatically write changes
   into XMP** is unchecked. First cancel and test an unchecked plugin confirmation:
   no rating must change. The plugin never changes this preference. Do not run a
   write test while automatic writing is enabled or its state is unverified.
6. **Apply stars** must show the catalog, service, plan identifier and exact changes.
   Only explicitly authorized changes from zero to one star are allowed. Excluded,
   already rated or subsequently edited photos must remain unchanged. Develop
   settings, flags, labels, keywords and collections must match the baseline.
7. Repeat the operation and verify that no new changes occur. Manually change a
   rating after an application, then reimport the same photo and verify that the
   later manual rating is preserved. A service must not apply to another catalog.
8. Check **Outcome** in the web app. Partial outcomes must show skipped, conflicting
   and uncertain results separately. Use **Show candidates in Lightroom** to select
   the exact candidate identifiers without writing metadata or creating collections.

The local journal is written before each SDK rating change. After an uncertain
outcome, check the catalog rating; the plugin does not reapply automatically.
Running **Apply stars** again can submit an interrupted receipt.

## Additional cases

- Add photos to an existing service, including existing identifiers and duplicate
  file names. Only new previews should upload; existing baselines and decisions
  remain unchanged. Test interruption and resumption with the same selection.
- Prepare two plans, confirm one, then interrupt application. Resumption must use
  the active plan. Cancellation while waiting for catalog write access must prevent
  a rating change for a photo that has not started.
- Hide candidates with a source or filter and run **Show candidates in Lightroom**.
  The plugin must report a partial selection rather than silently claim success.
- Verify that the Guide menu and Guide buttons work with the backend stopped.
- Confirm that the Italian plugin, its token and runtime data remain untouched.

## Validation status

Automated tests use synthetic fixtures and simulated official SDK interfaces.
They do not access Lightroom catalogs. The English edition still requires its own
manual native-dialog and end-to-end test on an explicitly authorized sample.

Upstream issues covered by regression tests include unavailable `os.rename` in the
Adobe runtime, interrupted state writes, and the required JSON `null` completion
payload for a new import. State persistence uses `LrFileUtils.move` and preserves
pending/previous copies; it never reads or writes the Lightroom catalog database.
