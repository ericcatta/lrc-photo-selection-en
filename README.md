# LrC Photo Selection — English edition

**A guided first selection of photographs, ready to review in Lightroom Classic.**

[🇮🇹 Italian edition](https://github.com/ericcatta/lrc-photo-selection) · **English edition**

LrC Photo Selection connects a Lightroom Classic plugin to a web application running on your Mac. Start with a selected set of photographs, describe what you want to keep, review the proposal, and send the confirmed selection back to Lightroom as star ratings. This edition's interface, plugin dialogs, guide and documentation are in English. Your own instructions are preserved exactly as you enter them.

The goal is not simply to keep the sharpest photographs. Your instructions, distinct situations, expression, composition and photographic meaning take priority. A memorable but technically imperfect photograph can be more useful than another polished near-duplicate.

> This is an early working project. AI proposals need human review; they do not guarantee correct recognition of subjects, people or situations.

## What it does

- One editable instruction field, optional editable presets and saved preset versions per service.
- **Local only**, **Local + OpenAI**, and **Directly OpenAI** workflows. Local operation does not need an OpenAI key.
- Separate local candidate and final OpenAI quantity targets.
- A contact sheet with filters, manual inclusion/exclusion, locked choices, undo/redo, two-photo comparison, and a large navigable preview. Use **← →** to browse and **Esc** to close the preview.
- **Distinct situations first:** choose one representative from each eligible group before adding more variants. Photographic merit orders the alternatives within each group.
- Balanced extra rounds: if there are 10 distinct groups and the target is 20, add a second choice from each group when available, rather than taking all extras from one group.
- A **soft target**: 23 situations may produce 23 candidates even when the requested quantity is 20. Manual inclusions, category coverage and uncertain photographs can also exceed the target.
- Explicit OpenAI review and confirmation, including the exact sample, model, new and reusable evaluations, and estimated cost when known. Variety is assessed only within the confirmed sample.
- Persistent local services, incremental imports within the same catalog, and archiving without deleting the service.

## What changes in Lightroom

**The only photograph-data change is assigning one star to eligible candidates that currently have zero stars**, after preview and confirmation in both the web application and Lightroom.

Existing ratings are never lowered or removed. Excluding a photograph in the web app does not delete its file or remove its stars. The plugin does not alter develop settings, flags, color labels, keywords or collections. It does not move, rename or delete originals or sidecars.

**Show candidates in Lightroom** changes only the temporary selection in the current view. All Lightroom access uses Adobe's official Lua SDK; the catalog database is never accessed directly.

## Easiest installation on a Mac

There is no packaged application installer yet. Download the project and set up its local environment once. The supported installation path is **macOS with Lightroom Classic**. Running the optional MLX vision model locally requires **Apple Silicon**.

### 1. Install the prerequisites

Install these if they are not already available:

- **Python 3.11 or later** from [python.org](https://www.python.org/downloads/macos/).
- **Node.js and npm** from [nodejs.org](https://nodejs.org/en/download). Use Node 20.19+ within the 20.x series, or 22.12 or later.
- **Lightroom Classic**. The plugin declares SDK minimum version 12; the original edition has been manually exercised in Lightroom Classic 16 on a Mac. This English edition requires its own native-dialog acceptance check.

Reopen Terminal after installing them and check:

```sh
python3 --version
node --version
npm --version
```

### 2. Download and install this edition

On GitHub choose **Code → Download ZIP**, extract the download and move the folder to a permanent location. Alternatively:

```sh
git clone https://github.com/ericcatta/lrc-photo-selection-en.git
cd lrc-photo-selection-en
```

Double-click **`scripts/install.command`**. It checks the prerequisites, creates a `.venv` inside this project, installs Python dependencies and builds the web interface. Internet access is needed to download dependencies.

If macOS does not open the file, run it from Terminal in the project directory:

```sh
zsh scripts/install.command
```

Installation does not download AI models, launch Lightroom or transmit photographs. The equivalent manual installation is:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
npm --prefix web ci
npm --prefix web run build
```

### 3. Start the local application

Double-click **`scripts/start.command`** and leave its Terminal window open. Or run:

```sh
.venv/bin/lrc-selection
```

The English backend listens only on **http://127.0.0.1:8766**. It never opens Lightroom or a catalog automatically. Stop it with **Ctrl+C** in its Terminal window.

The Italian edition uses port 8765. The English edition has separate application storage and credentials, so it does not reuse or overwrite the Italian edition's services or connection token.

### 4. Add the plugin to Lightroom

1. Open the catalog you intend to work in.
2. Choose **File → Plug-in Manager → Add**.
3. Select **`plugin/lrc-photo-selection.lrplugin`** inside this project. Keep the project at that location.
4. With the English backend running, choose **Library → Plug-in Extras → Configure local connection** for **Photo Selection (English)**.
5. If the dialog detects the local connection, choose **Connect**. The plugin stores the token securely and opens the web application.

If automatic detection fails, get the English edition's connection token from a second Terminal window in this project's directory:

```sh
.venv/bin/lrc-selection --show-connection
```

Paste it into the plugin's connection dialog. **This local token is not an OpenAI API key.** It connects the plugin and web application on your own computer. Keep it private.

The step-by-step guide is available from the plugin's **Guide** menu item and buttons, and from the web app. The Lightroom guide also works while the backend is stopped. Menu labels in Lightroom itself depend on your installed Lightroom language.

## Choose an analysis path

### Local only

The basic installation supports imports, manual review and a conservative engine that recognizes byte-identical derived previews. **Interpreting free-form instructions locally requires an explicitly installed vision model.** Importing photographs never downloads a model.

On an Apple Silicon Mac, run from the project directory:

```sh
.venv/bin/python -m pip install -e '.[local-instructions]'
.venv/bin/python scripts/setup_local_model.py --model Qwen3.5-9B-MLX-4bit --activate
```

The second command explicitly downloads model weights from Hugging Face. It requires several gigabytes of disk space and does not transmit photographs. Restart the backend afterwards. Performance depends on your Mac's memory and compute resources; photographic selection quality must be evaluated on your own authorized sample.

Without a local vision model, use manual review or **Directly OpenAI**. See [local model documentation](docs/models.md) for details and limitations.

### Local + OpenAI or Directly OpenAI

1. Open **OpenAI settings → OpenAI configuration** in the web app.
2. Enter and save your own OpenAI API key. The backend stores it in macOS Keychain, not in this repository or browser storage.
3. Choose **Check available models** to refresh the list for your account. This does not send photographs or change the selected model automatically.
4. Choose a compatible model and save. The interface distinguishes verified compatibility from compatibility inferred from a model family, and known from unknown prices.

When prices are available, the confirmation summary shows an estimate, a conservative reserve and an application-level limit for the send. A cumulative service budget is optional. **An estimate is not a guaranteed bill.**

Models without known prices remain selectable. Their summary explicitly states that cost is unavailable and requires confirmation without an estimate or enforceable monetary limit. Unknown prices are not presented as zero; a saved budget cannot constrain calls whose cost cannot be calculated.

The application does not check your account balance, purchase credits or enable automatic top-ups. Codex was used to develop the project; its authentication does not replace your own OpenAI API key. See [OpenAI analysis](docs/openai.md).

## Daily workflow: Lightroom → selection → Lightroom

The **Configure → Analyze → Review → Lightroom → Outcome** bar shows the next step. Viewing a step does not start an analysis, transmission or rating operation.

1. **Prepare a service in Lightroom.** Select the photographs and choose **Library → Plug-in Extras → Prepare service**. Create a new service or add the selection to an existing service from the same catalog. Wait for the previews; this does not start analysis or apply stars.
2. **Configure the web app.** Write your instructions or edit a preset, choose the path and set the quantities. For example: “Keep birds, portraits and landscapes, favoring different moments and compositions.” A general request for a varied selection is also valid.
3. **Start analysis.** The hybrid path offers **Continue with OpenAI** or **Use the local result** after local analysis. The direct path skips local preselection.
4. **Confirm any OpenAI send.** Review the sample, model, original text, quantity and cost information. The summary states how many of the imported photographs contribute to the variety assessment. Nothing is sent until you explicitly confirm. Only derived JPEG previews and contact sheets are sent, never RAW files or catalogs.
5. **Review the proposal.** Enlarge or compare photographs and use **Include/Exclude**. **All photos** also shows items outside the proposal. Uncertain items remain available for review. Confirming the selection does not apply stars.
6. **Preview stars in the web app.** Open the rating review, prepare the preview and confirm the exact list. Ten candidates may require only four new stars if the others already have ratings. Existing ratings are preserved.
7. **Apply in Lightroom.** In **Catalog Settings → Metadata**, verify that **Automatically write changes into XMP** (wording may vary by Lightroom version) is disabled. Then choose **Library → Plug-in Extras → Apply stars**, check the separate XMP attestation, review the list and confirm. The plugin checkbox does not change Lightroom's preference.
8. **Check the outcome.** The web app displays the plugin's receipt: applied, skipped and uncertain results. A partial outcome is not shown as complete success. **Show candidates in Lightroom** helps you locate the whole selection without creating a collection.

Groups remain provisional visual interpretations, not certified identities or equivalence claims. Manual decisions always prevail. Insufficient matching photographs or manual exclusions may make the target impossible; the application reports this instead of silently filling it with unsuitable photographs.

## Troubleshooting

| Situation | Next step |
| --- | --- |
| The local page does not open | Start `scripts/start.command`, leave its Terminal open and use port **8766** for this edition. |
| The plugin cannot connect | Start the English backend, configure the English plugin, and use this edition's `--show-connection` token if needed. Do not paste an OpenAI key here. |
| Local instructions are unavailable | Explicitly install and activate the local model, then restart the backend; or use Directly OpenAI. |
| An API analysis stops | Prepare a resume/new estimate and review new versus cached evaluations before confirming again. Cache reuse requires compatible images, instructions, model and format. |
| A request's outcome or cost is uncertain | It is not treated as free. Check the request log and OpenAI billing before authorizing another send. |
| Confirmation is disabled | Read the explanation beside the control: selected previews, saved settings or sufficient known-price reserve may be missing. |
| The proposal is empty | Review the instructions or include photographs manually. All files remain available. |
| XMP blocks rating application | Check Lightroom's catalog preference and separately attest to that check in the plugin dialog. |
| Some ratings are skipped | Read the receipt. Existing ratings and later manual changes are protected. |

Undo/redo affects web-app decisions. It does not withdraw API requests already sent or undo stars already applied in Lightroom.

## Updating

Stop the backend with **Ctrl+C**. For a Git installation, run `git pull`. For a ZIP installation, extract a fresh copy and add its `.lrplugin` folder in Plug-in Manager. Run `scripts/install.command` again and restart `scripts/start.command`.

After Lua changes, reload the plugin in Plug-in Manager. If your version has no reload control, remove its registration and add the folder again; if necessary restart Lightroom with your chosen catalog. Refreshing the browser does not reload Lightroom's Lua code.

This edition stores services, previews, cache, plans and receipts under **`~/Library/Application Support/LrC Photo Selection EN/`**. Updating code does not require deleting this directory. Do not publish it: it can contain photographs and personal information. The [Italian edition](https://github.com/ericcatta/lrc-photo-selection) has its own storage, port and plugin identity.

## Tests and limitations

The original edition's Lightroom → web → Lightroom path was manually tested on an authorized sample, including stars. Automated checks use synthetic photographs and simulated SDK/API responses. The new grouping policy and English translation require manual acceptance on your own sample; they are not evidence of universal photographic accuracy.

```sh
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest -q
npm --prefix web test -- --run
npm --prefix web run build
```

The optional Apple Vision test needs the compiled helper on macOS. Browser smoke scripts require Google Chrome and built assets; they start isolated synthetic backends without opening Lightroom or using the real OpenAI API. See [validation](docs/validation.md), [requirements](docs/requirements.md), [architecture](docs/architecture.md), [models](docs/models.md), [plugin guide](docs/plugin-guide.md), and [exchange protocol](shared/README.md).

The contact sheet and OpenAI picker render rows near the visible area while keeping the complete selection available. See [performance and the 5,000-photo synthetic test](docs/performance.md).
