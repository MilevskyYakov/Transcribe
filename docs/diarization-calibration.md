# Diarization Calibration

## Scope
- Goal: compare current `resemblyzer` quality signals across richer local fixtures and decide whether the warning thresholds are directionally useful.
- Date: 2026-04-29
- Config: `configs/lightweight_diarization.yaml`

## Current thresholds
- `min_centroid_similarity_margin < 0.10` -> `low cluster separation`
- `detected_cluster_count_max < 2` -> `fewer than 2 clusters`
- `dominant_cluster_share >= 0.80` with `segment_count >= 4` -> `imbalanced speaker clusters`

## Observations
| Fixture | Output | Status | Segments | Min Margin | Avg Margin | Dominant Share | Warnings | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `sample_data/smoke_duo.wav` | `output_smoke_duo_baseline_calibrated/` | `completed` | `2` | `0.25` | `0.25` | `0.50` | none | Clean balanced baseline |
| `sample_data/smoke_duo_rich.wav` | `output_smoke_duo_rich_calibrated/` | `completed` | `6` | `0.11` | `0.12` | `0.50` | none | Harder balanced alternation, close to current margin threshold |
| `sample_data/smoke_duo_imbalanced.wav` | `output_smoke_duo_imbalanced/` | `completed_with_warnings` | `6` | `0.14` | `0.15` | `0.83` | `imbalanced speaker clusters` | Useful positive case for dominant-share warning |
| `sample_data/smoke_duo_overlap.wav` | `output_smoke_duo_overlap/` | `completed_with_warnings` | `6` | `0.26` | `0.30` | `0.83` | `imbalanced speaker clusters` | Overlap did not reduce margin, but did collapse speaker balance |

## Takeaways
- The current `0.10` margin threshold is conservative enough to avoid warning on both balanced fixtures.
- The richer balanced fixture already reaches `0.11`, so increasing the threshold above `0.10` would likely create false positives.
- The `0.80` dominant-cluster-share threshold successfully catches both the intentionally imbalanced fixture and the overlap-heavy fixture.
- Overlap is not reliably exposed by margin alone; the balance-based signal adds real coverage.

## Recommended next move
- Keep `min_centroid_similarity_margin = 0.10` for now.
- Keep `dominant_cluster_share = 0.80` for now.
- Add one more fixture where speakers are balanced by count but uneven by duration, to test whether duration-aware balance is needed in addition to segment-count balance.
