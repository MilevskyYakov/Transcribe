"""Measure speaker-turn attribution and the proposed degraded-mode gate."""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
from typing import Any


def _score(expected: list[str], predicted: list[str], overlap_label: str) -> dict[str, float]:
    if not expected or len(expected) != len(predicted):
        raise ValueError("Expected and predicted labels must have the same non-zero length")
    reference_speakers = sorted({label for label in expected if label != overlap_label})
    predicted_speakers = sorted(set(predicted))
    if not reference_speakers or len(predicted_speakers) > len(reference_speakers):
        raise ValueError("Predicted speaker count must not exceed reference speaker count")

    best_correct = -1
    best_false = len(expected)
    for assignment in itertools.permutations(reference_speakers, len(predicted_speakers)):
        mapping = dict(zip(predicted_speakers, assignment))
        mapped = [mapping[label] for label in predicted]
        correct = sum(
            actual == wanted
            for wanted, actual in zip(expected, mapped)
            if wanted != overlap_label
        )
        false = sum(wanted != actual for wanted, actual in zip(expected, mapped))
        if (correct, -false) > (best_correct, -best_false):
            best_correct, best_false = correct, false

    speaker_turns = sum(label != overlap_label for label in expected)
    return {
        "speaker_turn_accuracy": round(best_correct / speaker_turns, 3),
        "false_label_rate": round(best_false / len(expected), 3),
    }


def _gate(quality: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    cluster_count = quality.get("detected_cluster_count_max")
    if not isinstance(cluster_count, int) or cluster_count < 2:
        reasons.append("fewer_than_two_clusters")
    margin = quality.get("min_centroid_similarity_margin")
    if isinstance(cluster_count, int) and cluster_count >= 2 and (
        not isinstance(margin, (int, float)) or margin < contract["min_centroid_margin"]
    ):
        reasons.append("low_cluster_separation")
    dominant_share = quality.get("dominant_cluster_share")
    if (
        quality.get("segment_count", 0) >= contract["min_segments_for_imbalance"]
        and isinstance(dominant_share, (int, float))
        and dominant_share >= contract["max_dominant_cluster_share"]
    ):
        reasons.append("imbalanced_clusters")
    return {
        "mode": "transcript_without_labels" if reasons else "reliable_labels",
        "reason_codes": reasons,
    }


def run_probe(payload: dict[str, Any]) -> dict[str, Any]:
    contract = payload["contract"]
    overlap_label = contract["overlap_label"]
    candidates = sorted(
        {candidate for fixture in payload["fixtures"] for candidate in fixture["predictions"]}
    )
    result: dict[str, Any] = {
        "origin": payload.get("origin"),
        "contract": contract,
        "candidates": {},
    }
    for candidate in candidates:
        fixtures = []
        for fixture in payload["fixtures"]:
            if candidate not in fixture["predictions"]:
                continue
            score = _score(fixture["expected_labels"], fixture["predictions"][candidate], overlap_label)
            gate = _gate(fixture["quality"], contract)
            actual_reliable = (
                score["speaker_turn_accuracy"] >= contract["min_speaker_turn_accuracy"]
                and score["false_label_rate"] <= contract["max_false_label_rate"]
            )
            fixtures.append(
                {"name": fixture["name"], **score, "actual_reliable": actual_reliable, "gate": gate}
            )

        degraded = [fixture for fixture in fixtures if fixture["gate"]["mode"] == "transcript_without_labels"]
        labeled = [fixture for fixture in fixtures if fixture["gate"]["mode"] == "reliable_labels"]
        result["candidates"][candidate] = {
            "fixtures": fixtures,
            "mean_speaker_turn_accuracy": round(
                sum(fixture["speaker_turn_accuracy"] for fixture in fixtures) / len(fixtures), 3
            ),
            "mean_false_label_rate": round(
                sum(fixture["false_label_rate"] for fixture in fixtures) / len(fixtures), 3
            ),
            "degraded_mode_precision": round(
                sum(not fixture["actual_reliable"] for fixture in degraded) / len(degraded), 3
            ) if degraded else None,
            "reliable_labels_precision": round(
                sum(fixture["actual_reliable"] for fixture in labeled) / len(labeled), 3
            ) if labeled else None,
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.fixture.read_text(encoding="utf-8"))
    print(json.dumps(run_probe(payload), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())