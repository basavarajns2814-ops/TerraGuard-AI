"""Binary change-mask evaluation metrics."""

from __future__ import annotations

import numpy as np


def calculate_metrics(prediction: np.ndarray, reference: np.ndarray) -> dict[str, float | int]:
    """Compute precision, recall, F1, and IoU with safe zero-denominator handling."""
    if prediction.shape != reference.shape:
        raise ValueError(
            f"Prediction and reference must have matching shapes, got "
            f"{prediction.shape} and {reference.shape}."
        )

    predicted = prediction.astype(bool)
    expected = reference.astype(bool)
    true_positive = int(np.count_nonzero(predicted & expected))
    false_positive = int(np.count_nonzero(predicted & ~expected))
    false_negative = int(np.count_nonzero(~predicted & expected))
    true_negative = int(np.count_nonzero(~predicted & ~expected))

    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    f1_score = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    iou = true_positive / (true_positive + false_positive + false_negative) if true_positive + false_positive + false_negative else 0.0

    return {
        "precision": precision,
        "recall": recall,
        "f1_score": f1_score,
        "iou": iou,
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "true_negative": true_negative,
    }
