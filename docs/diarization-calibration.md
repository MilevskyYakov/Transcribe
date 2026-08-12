# Diarization Calibration

## Scope and reproducibility

- Goal: measure speaker-turn attribution, false labels, and precision of a conservative `reliable_labels` / `transcript_without_labels` gate.
- Run: 2026-08-11 on macOS Apple Silicon, local CPU only.
- Config: `configs/lightweight_diarization.yaml` (`whisper/tiny`, Resemblyzer, automatic speaker count).
- Runtime: Python 3.11.15, `mnema` 0.1.1, Resemblyzer 0.1.4, scikit-learn 1.9.0, openai-whisper 20250625, NumPy 2.4.6, Torch 2.13.0.
- Fixture origin: synthetic macOS `say` voices already committed under `sample_data`; no user recordings. The JSON-only rapid-interruption case is in `tests/fixtures/diarization_probe.json`.

Reproduce audio runs:

```bash
for name in smoke_duo smoke_duo_rich smoke_duo_imbalanced smoke_duo_overlap; do
  .venv/bin/python -m mnema.cli.main \
    --config configs/lightweight_diarization.yaml \
    run "sample_data/${name}.wav" \
    --speaker-manifest "sample_data/${name}_speakers.json" \
    --out "/tmp/transcribe-issue-59/${name}"
done
```

Reproduce attribution and gate metrics:

```bash
.venv/bin/python scripts/diarization_probe.py tests/fixtures/diarization_probe.json
```

## Pipeline boundary

Current flow is:

`ASR segments -> pause splitting -> one embedding per whole segment -> clustering -> short A-B-A smoothing -> quality summary -> optional expected-name mapping -> artifacts/export -> speaker review`.

Three consequences matter:

1. A segment is the smallest diarization unit. If it contains overlapping voices or a turn not exposed by ASR word timings, Resemblyzer must assign one label to mixed audio.
2. `smooth_speaker_turns` rewrites a short low-margin A-B-A turn to A-A-A. That rule cannot distinguish a clustering glitch from a real interruption.
3. `collect_diarization_quality_warnings` has no caller. Quality is stored in `job.metadata.diarization_quality`, but low-quality jobs still finish as `completed`, keep labels, and enter speaker review/export.

There is also no minimum usable speech duration before embedding: the backend test accepts a three-sample, 0.0002-second slice. Existing `DiarizationQualityResponse` already carries cluster count, margin, dominant share, unmapped count, switch count, and total segment count, so the degraded contract does not need a new backend abstraction.

## Measurements

Speaker IDs are permutation-matched before scoring. `false label rate` includes wrong speaker labels and any single-speaker label assigned to an overlap reference.

| Fixture | Turns | Min margin | Dominant share | Turn accuracy | False labels | Proposed mode |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `smoke_duo.wav` | 2 | 0.25 | 0.50 | 1.00 | 0.00 | `reliable_labels` |
| `smoke_duo_rich.wav` | 6 | 0.21 | 0.50 | 1.00 | 0.00 | `reliable_labels` |
| `smoke_duo_imbalanced.wav` | 6 | 0.14 | 0.83 | 1.00 | 0.00 | `transcript_without_labels` |
| `smoke_duo_overlap.wav` | 6 | 0.26 | 0.83 | 0.60 | 0.50 | `transcript_without_labels` |
| synthetic rapid A-B-A | 3 | 0.04 | 0.67 | 0.67 | 0.33 | `transcript_without_labels` |

Observed overlap failures are concrete: two segments whose recognized text says `Меня зовут Марина` receive the mapped label `Алексей`; another mixed segment is forced to one speaker. Margin remains high at 0.26, so margin does not expose overlap.

Aggregate current-path metrics across five fixtures:

- mean speaker-turn accuracy: **0.853**;
- mean false-label rate: **0.167**;
- precision when labels are allowed by the proposed gate: **1.00**;
- degraded-mode precision: **0.667** (two real failures and one legitimate imbalanced false positive).

Removing only A-B-A smoothing changes the rapid-interruption case from 0.67/0.33 to 1.00/0.00 and aggregate accuracy from 0.853 to 0.920. It does not fix overlap. After that removal, degraded-mode precision falls to 0.333 because current quality signals conservatively suppress two otherwise correct cases.

The previous calibration values are not stable across the currently allowed dependency ranges: the rich fixture margin moved from about 0.11 to 0.21 while labels stayed correct. Thresholds therefore need versioned fixture checks; margin must not be treated as calibrated probability.

## Minimal local alternative

`pyannote.audio` `speaker-diarization-community-1` is the one realistic alternative worth a bounded spike because it performs speaker segmentation before clustering instead of embedding fixed ASR segments. Its open-source pipeline runs locally after model download and exposes both overlap-preserving `speaker_diarization` and single-speaker `exclusive_speaker_diarization`. The latter fits the current ASR segment contract; the former can supply overlap evidence. Current documentation also describes improved speaker counting/assignment over the older 3.1 pipeline.

It is not a drop-in production dependency:

- model access requires accepting Hugging Face conditions and an access token for the initial download;
- current package requires Python >=3.10, Torch >=2.8, torchaudio, torchcodec, and ffmpeg;
- it adds a large model/runtime to the packaged app;
- the model card uses CC-BY-4.0, so packaged distribution needs an attribution check;
- no Hugging Face credential is available in this repository, so this Issue does not fabricate an alternative score.

Sources:

- <https://github.com/pyannote/pyannote-audio#community-1-open-source-speaker-diarization>
- <https://huggingface.co/pyannote/speaker-diarization-community-1>
- <https://huggingface.co/pyannote/segmentation-3.0>
- <https://github.com/pyannote/pyannote-audio/blob/main/src/pyannote/audio/pipelines/speaker_diarization.py>
- <https://github.com/resemble-ai/Resemblyzer#demos>

Decision: do not replace Resemblyzer now. First ship the smaller safety slice below. Run a gated pyannote spike only if overlap fixtures must retain labels rather than degrade to chronological text.

Promotion gate for that later spike: frozen local gold set with at least 100 rapid-turn boundaries and 10 annotated overlap minutes; candidate DER <=15% and at least five percentage points better than Resemblyzer; overlap F1 >=0.70 with recall >=0.75; rapid-turn boundary F1 within ±250 ms >=0.85; speaker-attributed word accuracy outside overlap >=0.90; target-Mac p95 runtime <=2x Resemblyzer; cached rerun succeeds without network. These are promotion criteria, not measured results from this Issue.

## Proposed machine-readable contract

Store this under `job.metadata.diarization_confidence`:

```json
{
  "version": 1,
  "mode": "reliable_labels",
  "reason_codes": [],
  "metrics": {
    "detected_cluster_count": 2,
    "min_centroid_margin": 0.21,
    "dominant_cluster_share": 0.5
  },
  "thresholds": {
    "min_centroid_margin": 0.1,
    "max_dominant_cluster_share": 0.8,
    "min_segments_for_imbalance": 4
  }
}
```

Allowed values:

- `reliable_labels`: at least two clusters, margin >=0.10, and no count imbalance >=0.80 for four or more segments;
- `transcript_without_labels`: any condition fails; `reason_codes` contains `fewer_than_two_clusters`, `low_cluster_separation`, or `imbalanced_clusters`.

For `transcript_without_labels`, preserve segment chronology, timestamps, words, raw/clean text, and diagnostic metadata; remove user-facing `speaker_label`/mapping, skip speaker review and expected-name mapping, and export Markdown without speaker headings. This is deliberately precision-first. It cannot prove that balanced overlap is safe because the current backend emits no overlap signal.

## Exact implementation slice for #60

1. Stop calling `smooth_speaker_turns`; deletion is safer than another heuristic because the current rule measurably destroys real short turns.
2. Add one gate function beside `collect_diarization_quality_summary` that returns the contract above.
3. Apply the gate once after diarization and before expected-name mapping/export. Strip labels only in degraded mode; never alter text or timing.
4. Persist the contract in job metadata and make speaker review return `not_required` when mode is degraded.
5. Keep the five probe cases as regression evidence. Add app/API tests that degraded jobs show chronological unlabeled text and never offer names.

Do not add pyannote, biometric identity, voice memory, cloud calls, or a new ML abstraction in this slice.