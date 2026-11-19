# OpenAI analysis: consent and budget

The local backend uses the Responses API. Codex is the development tool; its
credentials are not used for photographic API analysis. The English edition uses
separate local storage and the `lrc-photo-selection-en-openai` keychain service.

## Workflow

1. Save an API key in the web app’s OpenAI settings. The backend stores it in the
   macOS keychain, never returning it to the frontend or writing it to logs or Git.
2. Choose Local + OpenAI or Directly OpenAI. Local analysis is optional. Select
   previews from the local proposal or all imported previews. The comparison covers
   only the confirmed sample, not photos excluded from transmission.
3. Set the final OpenAI quantity separately from the local target. Request an estimate
   without a mandatory overall budget. Estimation makes no OpenAI call and sends no
   images. With known pricing, confirmation authorizes the displayed conservative
   per-plan guard; an overall budget remains optional. Unknown pricing instead
   requires explicit consent to transmit without a verified monetary estimate/guard.
4. Review the exact sample, previews, model, original text, final quantity, estimate,
   conservative limit and previous usage.
5. Explicitly confirm transmission. Only this action enables the displayed plan’s
   requests. Changes to data, criteria, model or revision require a new estimate and
   confirmation.

Saved instructions are sent as a separate user `input_text` element, unchanged down
to Unicode, line breaks and spaces. The interface has one editable text field.
Legacy criteria are visibly appended while preserving original text as a prefix;
only explicit saving consolidates fields. Technical schemas and derived categories
never replace the saved original. Transmission includes only confirmed previews,
never RAW files, catalogs, original paths or credentials in prompts. Previews may
still contain visible personal data, hence the exact sample confirmation.
`store:false` disables later response retrieval through the API; it is not a claim
that OpenAI maintains no service logs.

## Estimates and historical pricing verification

The following rates record upstream verification dates, not a fresh pricing claim:

| Verified date | Model | Input / output USD per million tokens |
|---|---|---:|
| November 18, 2026 | GPT-5.4 mini (`gpt-5.4-mini-2026-03-17`) | 0.75 / 4.50 |
| November 18, 2026 | GPT-5.4 (`gpt-5.4-2026-03-05`) | 2.50 / 15.00 |
| November 19, 2026 | GPT-6.2 Sol | 2.00 / 10.00 |
| November 19, 2026 | GPT-6.2 Astra | 8.00 / 40.00 |
| November 19, 2026 | GPT-5.3 Codex, deprecated but account-visible | 1.75 / 14.00 |

Conservative estimates assume no cache discount. Pricing has a validity window;
expired rates become unknown for new plans. Unknown prices are never shown as zero.
The reserve accounts for output limits, conservative text/image input bounds and
an additional margin. It is neither a quality measure nor a guaranteed exact cost.
Returned usage is recorded and cost calculated using plan rates; the provider bill
remains authoritative. The guard is application-side, not an OpenAI account limit.

## Interruption and resumption

Requests are sequential, without unlimited automatic retries. Conservative cost is
reserved before transmission; service budgets include prior usage and reserves.
Timeouts and uncertain outcomes retain their reserve rather than being treated as
free calls. Cancellation stops later requests but cannot recall an already sent one.

Valid results are reused only when preview, original instructions/criteria, model
and format version match. Resumption requires a new estimate and confirmation.
Restarting the backend never resumes cloud sends automatically. Local work can
continue independently. Unrelated photos never fill missing/incomplete matches.
Responses with verifiable usage but unusable photo output are retained as Needs review; errors
in transport, usage validation, interpretation or global comparison still suspend
when required for safe continuation.

API outputs are review proposals, not Lightroom mutations. Manual decisions,
existing stars and originals remain protected by the separate star workflow.

## Credits

No balance or nominal account credit is assumed. Local budgets are distinct from
provider credits and terms. The app purchases no credits and enables no automatic
top-up. Check credit and expiry in the account before testing; applicable conditions
can depend on subscription and billing cycle.

## Dynamic models

Verify available models reads `/v1/models` with the saved key, without photographs.
The list is cached locally with its verification date and a refresh reminder after
24 hours. Candidate image/Responses families remain selectable without known
pricing. The UI distinguishes reviewed compatibility from family-inferred
compatibility: an account listing alone proves neither image support nor pricing.
Audio-only, embedding and image-generation models are excluded. Selection never
changes automatically. Replacing the key invalidates cached availability.

The reviewed registry remains separate from dynamic availability. Prices are not
inferred from model names. Reasoning parameters adapt by family; GPT-6.2 uses
`low`, not `none`. Refreshing models performs no inference or photo transmission.

## Final quantity and whole-sample selection

After completed analysis, another final quantity can reuse stored evaluations
without new requests. It cannot recover information about photographs never
included in the confirmed sample.

Priorities are original instructions, requested-category coverage and series
variety, then photographic merit among relevant alternatives. A quality score must
not replace one requested category with another. Categories remain interpretations;
missing/uncertain coverage is reported rather than filled with unrelated images.
Expression, gesture, composition and meaning can outweigh sharpness. Visual merit
is a subjective ordinal judgment, not calibrated beauty, and explicit preferences
prevail.

The plan includes text interpretation, individual preview assessments and global
comparison using indexed JPEG contact sheets of 16 images plus all sample
assessments. Each request keeps the exact original user text separate. Estimates
include interpretation and global comparison. No photographs outside the confirmed
list are added. Small contact-sheet details remain uncertain; missing or invalid
global comparison is never presented as completed.

Local analysis also aggregates evidence across imported previews, categories and
visual vectors. It does not display all photographs simultaneously to the local
VLM. Older category-less caches are invalidated by engine version.

## Unknown pricing

The summary shows Cost unavailable and requires distinct consent for sending
without monetary budget enforcement. The stored budget is preserved. Available
token counts and unpriced requests are recorded; known monetary totals are labeled
partial and overall remaining funds unverifiable. Provider billing is authoritative.

## Situations before variants

Global comparison returns a complete partition of matching indices into near-duplicate
alternative groups with reasons. A broad category or location is insufficient to
merge photographs. The backend keeps one representative per group, even above the
target, then adds variants from less represented groups. Manual inclusions prevail
and count toward group occupancy.

This default applies without the word variety. Ranking chooses variants; it does
not authorize sacrificing a distinct situation for a stronger duplicate. A new
global format invalidates only global cache, leaving compatible interpretation and
individual assessments reusable. Existing proposals are not rewritten on load.
New comparison always requires estimate and confirmation. Recomposition of old
ungrouped results groups only byte-identical previews and reports that limitation.

## Official references

- [GPT-5.4 mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini)
- [GPT-5.4](https://developers.openai.com/api/docs/models/gpt-5.4)
- [Images and vision](https://developers.openai.com/api/docs/guides/images-vision)
- [Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [ChatGPT/API credits](https://developers.openai.com/api/docs/guides/chatgpt-api-credits)
- [GPT-6.2 Sol](https://developers.openai.com/api/docs/models/gpt-6.2-sol)
- [GPT-6.2 Astra](https://developers.openai.com/api/docs/models/gpt-6.2-astra)
