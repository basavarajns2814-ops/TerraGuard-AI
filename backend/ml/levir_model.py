"""CPU trainable pixel classifier for LEVIR-CD paired RGB images."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import random
from typing import Any

import joblib
import numpy as np
from PIL import Image

from src.change_detection import predict_change
from src.data_loader import ImagePair, inspect_dataset, load_pair
from src.metrics import calculate_metrics

FEATURE_SCHEMA = "rgb_pair_abs_difference_local_mean_v1"
BASELINE_THRESHOLD = 30


def extract_features(earlier: np.ndarray, later: np.ndarray) -> np.ndarray:
    """Build per-pixel RGB, absolute-difference, and 3x3 local-difference features."""
    if earlier.shape != later.shape or earlier.ndim != 3 or earlier.shape[2] != 3:
        raise ValueError("Earlier and later images must be aligned RGB arrays.")
    a = earlier.astype(np.float32) / 255.0
    b = later.astype(np.float32) / 255.0
    difference = np.abs(a - b)
    mean_difference = difference.mean(axis=2)
    padded = np.pad(mean_difference, 1, mode="edge")
    local_mean = np.zeros_like(mean_difference)
    for row_offset in range(3):
        for column_offset in range(3):
            local_mean += padded[
                row_offset : row_offset + mean_difference.shape[0],
                column_offset : column_offset + mean_difference.shape[1],
            ]
    local_mean /= 9.0
    return np.concatenate((a, b, difference, local_mean[..., None]), axis=2)


def load_classifier(path: str | Path) -> dict[str, Any]:
    """Load a trained artifact and reject incompatible feature layouts."""
    artifact = joblib.load(path)
    if artifact.get("feature_schema") != FEATURE_SCHEMA or "model" not in artifact:
        raise ValueError("The saved LEVIR model has an unsupported feature schema.")
    return artifact


def predict_probability(artifact: dict[str, Any], earlier: np.ndarray, later: np.ndarray) -> np.ndarray:
    features = extract_features(earlier, later)
    shape = features.shape[:2]
    probability = artifact["model"].predict_proba(features.reshape(-1, features.shape[-1]))[:, 1]
    return probability.reshape(shape).astype(np.float32)


def _sample_training_pixels(
    pairs: tuple[ImagePair, ...], *, seed: int, samples_per_class_per_pair: int = 192
) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    feature_rows: list[np.ndarray] = []
    target_rows: list[np.ndarray] = []
    for pair in pairs:
        earlier, later, label = load_pair(pair)
        target_size = (max(1, earlier.shape[1] // 2), max(1, earlier.shape[0] // 2))
        earlier = np.asarray(Image.fromarray(earlier).resize(target_size, Image.Resampling.BILINEAR))
        later = np.asarray(Image.fromarray(later).resize(target_size, Image.Resampling.BILINEAR))
        label = np.asarray(
            Image.fromarray(label.astype(np.uint8) * 255).resize(target_size, Image.Resampling.NEAREST)
        ) > 0
        features = extract_features(earlier, later).reshape(-1, 10)
        flat_label = label.reshape(-1)
        positive = np.flatnonzero(flat_label)
        negative = np.flatnonzero(~flat_label)
        for indexes, target in ((positive, 1), (negative, 0)):
            if not indexes.size:
                continue
            count = min(samples_per_class_per_pair, indexes.size)
            chosen = rng.choice(indexes, size=count, replace=False)
            feature_rows.append(features[chosen])
            target_rows.append(np.full(count, target, dtype=np.uint8))
    if not feature_rows:
        raise ValueError("No labeled training pixels were available.")
    return np.concatenate(feature_rows), np.concatenate(target_rows)


def split_training_pairs(
    train_pairs: tuple[ImagePair, ...], *, seed: int = 42, validation_fraction: float = 0.10
) -> tuple[tuple[ImagePair, ...], tuple[ImagePair, ...]]:
    """Deterministically divide only the supplied official training pairs."""
    if not 0 < validation_fraction < 1:
        raise ValueError("Validation fraction must be between zero and one.")
    shuffled = list(train_pairs)
    random.Random(seed).shuffle(shuffled)
    validation_count = max(1, round(len(shuffled) * validation_fraction))
    return tuple(shuffled[validation_count:]), tuple(shuffled[:validation_count])


def _add_counts(total: dict[str, int], metrics: dict[str, float | int]) -> None:
    for key in ("true_positive", "false_positive", "false_negative", "true_negative"):
        total[key] += int(metrics[key])


def _summary(counts: dict[str, int]) -> dict[str, float | int]:
    tp, fp, fn, tn = (counts[k] for k in ("true_positive", "false_positive", "false_negative", "true_negative"))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        **counts,
        "precision": precision,
        "recall": recall,
        "f1_score": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "iou": tp / (tp + fp + fn) if tp + fp + fn else 0.0,
    }


def _validation_threshold(
    classifier: Any, validation_pairs: tuple[ImagePair, ...]
) -> tuple[float, dict[str, float | int]]:
    candidates = (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8)
    totals = {threshold: {key: 0 for key in ("true_positive", "false_positive", "false_negative", "true_negative")} for threshold in candidates}
    for pair in validation_pairs:
        earlier, later, reference = load_pair(pair)
        target_size = (max(1, earlier.shape[1] // 2), max(1, earlier.shape[0] // 2))
        earlier = np.asarray(Image.fromarray(earlier).resize(target_size, Image.Resampling.BILINEAR))
        later = np.asarray(Image.fromarray(later).resize(target_size, Image.Resampling.BILINEAR))
        reference = np.asarray(
            Image.fromarray(reference.astype(np.uint8) * 255).resize(target_size, Image.Resampling.NEAREST)
        ) > 0
        features = extract_features(earlier, later)
        probabilities = classifier.predict_proba(features.reshape(-1, 10))[:, 1].reshape(reference.shape)
        for threshold in candidates:
            _add_counts(totals[threshold], calculate_metrics(probabilities >= threshold, reference))
    scored = [(float(_summary(totals[t])["f1_score"]), t) for t in candidates]
    _, best = max(scored, key=lambda item: (item[0], item[1]))
    return best, _summary(totals[best])


def evaluate_final_test(
    artifact: dict[str, Any], test_pairs: tuple[ImagePair, ...]
) -> dict[str, Any]:
    """Perform one fixed final evaluation using all supplied official test pairs."""
    baseline_counts = {key: 0 for key in ("true_positive", "false_positive", "false_negative", "true_negative")}
    model_counts = baseline_counts.copy()
    per_image: list[dict[str, Any]] = []
    for pair in test_pairs:
        earlier, later, reference = load_pair(pair)
        baseline = predict_change(earlier, later, BASELINE_THRESHOLD)
        probability = predict_probability(artifact, earlier, later)
        model_mask = probability >= float(artifact["threshold"])
        baseline_metrics = calculate_metrics(baseline, reference)
        model_metrics = calculate_metrics(model_mask, reference)
        _add_counts(baseline_counts, baseline_metrics)
        _add_counts(model_counts, model_metrics)
        per_image.append({
            "image_pair": pair.name,
            "baseline": {key: baseline_metrics[key] for key in ("precision", "recall", "f1_score", "iou")},
            "trained_model": {key: model_metrics[key] for key in ("precision", "recall", "f1_score", "iou")},
        })
    return {
        "dataset_split": "official test",
        "test_pair_count": len(test_pairs),
        "baseline_threshold": BASELINE_THRESHOLD,
        "model_threshold_selected_on_training_validation": float(artifact["threshold"]),
        "baseline_micro": _summary(baseline_counts),
        "trained_model_micro": _summary(model_counts),
        "per_image": per_image,
        "test_used_for_training_or_threshold_selection": False,
    }


def train_and_evaluate(
    dataset_root: str | Path,
    model_path: str | Path,
    report_path: str | Path,
    *,
    seed: int = 42,
    validation_fraction: float = 0.10,
    samples_per_class_per_pair: int = 64,
    max_iter: int = 20,
    max_bins: int = 31,
) -> dict[str, Any]:
    """Split official train only, fit/select using validation, then evaluate test once."""
    from sklearn.ensemble import HistGradientBoostingClassifier

    root = Path(dataset_root)
    train_inspection = inspect_dataset(root / "train")
    test_inspection = inspect_dataset(root / "test")
    if not train_inspection.valid_pairs or not test_inspection.valid_pairs:
        raise ValueError("Official train and test splits must both contain valid image triples.")
    if len(train_inspection.valid_pairs) != 637 or len(test_inspection.valid_pairs) != 348:
        raise ValueError(
            "The audited LEVIR-CD+ split sizes changed; expected 637 training and "
            "348 official test pairs. No training or evaluation was started."
        )
    if train_inspection.errors or test_inspection.errors:
        raise ValueError("Unreadable or dimension-mismatched data exists in an official split.")
    fit_pairs, validation_pairs = split_training_pairs(
        train_inspection.valid_pairs, seed=seed, validation_fraction=validation_fraction
    )
    samples, targets = _sample_training_pixels(
        fit_pairs, seed=seed, samples_per_class_per_pair=samples_per_class_per_pair
    )
    classifier = HistGradientBoostingClassifier(
        learning_rate=0.1,
        max_iter=max_iter,
        max_bins=max_bins,
        max_leaf_nodes=15,
        min_samples_leaf=30,
        l2_regularization=1.0,
        early_stopping=False,
        random_state=seed,
    )
    classifier.fit(samples, targets)
    threshold, validation_metrics = _validation_threshold(classifier, validation_pairs)
    artifact = {
        "feature_schema": FEATURE_SCHEMA,
        "model": classifier,
        "threshold": threshold,
        "training_config": {
            "model": "HistGradientBoostingClassifier",
            "seed": seed,
            "official_train_pairs": len(train_inspection.valid_pairs),
            "fit_pairs": len(fit_pairs),
            "validation_pairs": len(validation_pairs),
            "validation_fraction": validation_fraction,
            "samples_per_class_per_fit_pair": samples_per_class_per_pair,
            "training_validation_resolution_scale": 0.5,
            "sampled_training_pixels": int(len(targets)),
            "max_iter": max_iter,
            "max_bins": max_bins,
            "validation_selected_probability_threshold": threshold,
        },
    }
    model_file = Path(model_path)
    report_file = Path(report_path)
    model_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, model_file, compress=3)

    # The official test split is first consumed here, after model and threshold are fixed.
    final_report = evaluate_final_test(artifact, test_inspection.valid_pairs)
    final_report.update({
        "feature_schema": FEATURE_SCHEMA,
        "training_config": artifact["training_config"],
        "validation_micro": validation_metrics,
        "model_artifact": str(model_file),
        "official_test_pair_count_detected": len(test_inspection.valid_pairs),
        "official_test_pair_count_expected": 348,
    })
    report_file.write_text(json.dumps(final_report, indent=2), encoding="utf-8")
    return final_report
