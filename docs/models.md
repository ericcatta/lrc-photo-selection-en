# Models: preliminary evaluation, no general performance claim

The upstream test machine was an M1 Max with 64 GB RAM. The active upstream local
model is Qwen3.5-9B MLX 4-bit with MLX-VLM 0.4.3, explicitly chosen by the owner after
synthetic testing. The previous Qwen3-VL-4B weights were removed. General category
coverage and photographic selection quality are not validated by this choice.
The English edition does not inherit the Italian installation or runtime data.

## Initial candidates and primary evidence

| Candidate | Primary evidence | Initial decision |
|---|---|---|
| SigLIP 2 base | [Model card](https://huggingface.co/google/siglip2-base-patch16-224), image/text encoder, Apache-2.0 | First optional encoder; load only from a pinned local revision. Similarity does not establish equivalence. |
| DINOv3 ViT-S | [Model card](https://huggingface.co/facebook/dinov3-vits16-pretrain-lvd1689m), gated with Meta-specific license | Deferred pending access and license review before download. |
| Mapika decider-4b | [Weights](https://huggingface.co/Mapika/decider-4b), [code](https://github.com/Mapika/decider), structured visual decisions; weights declared Apache-2.0 with training-data caveats | Mac visual compatibility not demonstrated; not installed initially. |
| LFM2.5-VL-3B | [Official Apple Silicon export](https://huggingface.co/LiquidAI/LFM2.5-VL-3B-MLX-8bit) | Candidate under LFM Open License v1.0 conditions; distinct from the text-only 24B-A2B model. |
| Qwen3-VL-4B | [Model card](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct), Apache-2.0, MLX conversion available | Initial visual baseline for later comparison. |
| Apple Vision | [Object detection documentation](https://developer.apple.com/documentation/vision/detecting-objects-in-still-images) | Local faces/landmarks, without identity recognition. |
| InsightFace | [Model zoo](https://github.com/deepinsight/insightface/blob/master/python-package/docs/model_zoo.md) | Weight licenses differ from code licenses; do not bundle noncommercial weights without review. |

LAION aesthetic predictors were not selected: checkpoint, license and validity
require verification if a measured problem warrants them. OpenJev, Laya,
SemIf-OpenJev and Bespoke-Nimble-9B were not adopted; image support, Mac availability
and commercial licensing must not be assumed. These are research leads, not dependencies.

## Benchmark protocol

Use an authorized, manually annotated sample covering changed people,
poses/laughter, bursts, unique imperfect moments, small/profile/occluded faces and
two cameras. Separate calibration and verification. Record sample IDs without
originals in Git, preview checksums, model/revision/runtime/resolution, criteria and
thresholds. First measure missed situations, incorrectly merged compositions,
unique images excluded and violated manual locks. Only then measure duplicates,
time, memory and cost. Arbitrary thresholds must not be described as validated.

Raw JSON files in `docs/benchmarks/` preserve original upstream Italian prompts and
model responses. They are evidence artifacts, intentionally untranslated. English
explanations here do not change those measured outputs or validate the English UI.

## Initial local runtime — November 18, 2026

- Qwen3-VL-4B-Instruct 4-bit conversion:
  `mlx-community/Qwen3-VL-4B-Instruct-4bit`, revision
  `2fd8dacbdb8f1e54b8c005f081ec5bf79c56376b`, declared Apache-2.0. MLX-VLM 0.3.9;
  effective dependencies are recorded in `requirements-local-ai-lock.txt`.
  Temporary inference previews were limited to 448 pixels, which can lose small
  subjects. No named identification was performed.
- SigLIP 2 base revision `75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2` was downloaded
  as an optional comparison adapter. It does not execute free-form instructions.
- Downloads are explicit through `scripts/setup_local_model.py`, never during
  import or analysis. Loading uses local directories with remote code disabled.
  Cache identity includes weight/configuration hashes and prompt revisions.

Sources: [Qwen](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct),
[MLX conversion](https://huggingface.co/mlx-community/Qwen3-VL-4B-Instruct-4bit),
[MLX-VLM](https://github.com/Neywa-Labs/mlx-vlm).

Valid JSON does not demonstrate correct understanding. Positive, negative,
preference, conflict and ambiguous-image cases require manual comparison.
Model outputs are interpretations, not imported facts.

## Subsequent hardware-aware research — November 18, 2026

Hardware was reconfirmed as a MacBook Pro M1 Max, 10 CPU cores and 64 GB unified
memory. Collection latency matters as well as whether weights fit in memory.

| Candidate | Assessment for this project |
|---|---|
| Qwen3.5-9B MLX 4-bit | Preferred candidate for another test: visual/text model, Apache-2.0, approximately 6 GB of weights. Vendor benchmarks are not culling or quantization-specific measurements. |
| Existing Qwen3-VL-4B | Smaller and integrated. The earlier 150/160 failure included integration defects and does not alone condemn the model. Retained as a technical comparison baseline. |
| Qwen3-VL-8B | Apache-2.0 alternative; not installed because 9B was a more interesting candidate in a similar memory range, subject to workflow testing. |
| Qwen3-VL-32B | Quantization may fit 64 GB, but additional memory/latency lacked measured benefit. Not installed. |
| Liquid LFM2.5-VL-3B | Potential speed advantage, but specific LFM license and no demonstrated Italian culling advantage. Not installed. |
| Mapika decider-4b v3 | Image support with typed decisions over explicit options rather than a direct generative-interpreter replacement. Requires another adapter without measured benefit. |

Primary sources consulted: [Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B),
[Apache license](https://huggingface.co/Qwen/Qwen3.5-9B/blob/main/LICENSE),
[4-bit MLX export](https://huggingface.co/mlx-community/Qwen3.5-9B-MLX-4bit),
[Qwen3-VL-8B](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct),
[LFM2.5-VL-3B](https://huggingface.co/LiquidAI/LFM2.5-VL-3B),
[Decider v3](https://huggingface.co/Mapika/decider-4b),
[MLX-VLM](https://github.com/Neywa-Labs/mlx-vlm).

The 9B preference is an engineering choice, not proof that it is universally best.
These sources do not benchmark this owner’s preferences, service variety and
photographic merit. Whole-collection selection remains a pipeline responsibility.

## Synthetic comparison and superseded initial decision

`scripts/check_local_model.py` generates geometric shapes and uses Italian
instructions. It measures loading, MLX memory and structured responses through the
same offline adapter, with thinking disabled. It accesses no user services or
photographs and does not evaluate aesthetics.

| Configuration | Expected checks passed | Total time | Peak MLX memory |
|---|---:|---:|---:|
| Qwen3-VL-4B, runtime 0.3.9 | 2/5 | 35.0 s | 4.27 GB |
| Qwen3.5-9B, isolated runtime 0.4.3 | 3/5 | 93.4 s | 7.70 GB |

The initial decision was **not to activate the replacement**: 9B recognized the red
circle and blue square but excluded each because the other category was absent,
violating collection-level coverage. The 4B failed to derive the geometric
categories and missed both positive cases. Both produced structurally valid output.
Runtime differences prevent attributing all differences to weights. Peak MLX memory
is not total Mac memory, and these times cannot be extrapolated to a wedding.

Complete raw reports: [4B](benchmarks/local-model-4b.json) and
[9B](benchmarks/local-model-9b.json). The candidate used MLX-VLM 0.4.3 extracted into
a temporary package without upgrading the active environment. The 9B weight
revision was `938d8919941c6e7efd3c7150eff7fe9d12afa631`; that candidate download was
removed following the negative test. No real photographs, decisions, stars or API
requests were involved.

Acceptance still requires distinct categories retained across images, no invented
same-photo co-occurrence requirement, correct positive/negative cases and then a
human comparison on the authorized real sample. Unit tests alone do not establish this.

## Later owner decision: activate Qwen3.5-9B anyway

After reviewing the negative coverage result, the owner explicitly requested the
9B replacement and removal of 4B. This superseded the initial decision above.
Qwen3.5-9B MLX 4-bit revision `938d8919941c6e7efd3c7150eff7fe9d12afa631` was adopted
with MLX-VLM 0.4.3. Installation started no new photo analysis and did not establish
coverage validity.

`local-model-selection.json` in local application storage explicitly selects the
active model. Setup supports `--model Qwen3.5-9B-MLX-4bit --activate`; analysis loading
remains offline. The previous 4B was removed only after provenance/file checks and
confirmation of the active selection. SigLIP 2 remains a separate encoder.

## November 19: integration revision v9

The reproduced category defect passed 11/11 controlled synthetic checks with the
same 9B model after integration revision v9. See the [v9 report](benchmarks/local-model-9b-v9.json)
and [validation history](validation.md). Earlier failures remain historical evidence;
weights and runtime were not replaced again. Real photographic selection quality
still requires manual validation.
