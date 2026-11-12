"""Generate publication figures from the recorded TerraGuard EXP-02 artifacts.

Run from the repository root with: python conference_paper/figures/make_figures.py
This script reads existing logs/reports/manifests only; it does not evaluate a model.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import Normalize


ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
RUN = ROOT / "training/experiments/EXP-02_SNUNet/runs/full_seed42_512_recovery_v2"
LOG = RUN / "training.log"
HISTORY = RUN / "history.json"
REPORT = ROOT / "training/experiments/EXP-02_SNUNet/reports/full_seed42_512_recovery_v2.json"
MANIFEST = ROOT / "training/manifests/split_seed_42.json"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.labelsize": 10,
    "legend.fontsize": 9,
    "figure.dpi": 120,
    "savefig.dpi": 300,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.22,
    "grid.linewidth": 0.6,
})


def save(fig: plt.Figure, stem: str) -> None:
    fig.savefig(OUT / f"{stem}.png", dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(OUT / f"{stem}.pdf", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def incomplete_note(ax: plt.Axes) -> None:
    ax.text(0.99, 0.02, "Run incomplete: 11/40 epochs", transform=ax.transAxes,
            ha="right", va="bottom", fontsize=8, color="#555555",
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.8, "pad": 2})


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    log_text = LOG.read_text(encoding="utf-8")
    log_pattern = re.compile(
        r"epoch=(\d+)/40\s+loss=([0-9.]+)\s+val_f1=([0-9.]+)\s+val_iou=([0-9.]+)"
    )
    records = {
        int(m.group(1)): {
            "training_loss": float(m.group(2)),
            "validation_f1": float(m.group(3)),
            "validation_iou": float(m.group(4)),
        }
        for m in log_pattern.finditer(log_text)
    }
    if sorted(records) != list(range(1, 12)):
        raise ValueError(f"Expected log records for epochs 1–11; found {sorted(records)}")

    history = json.loads(HISTORY.read_text(encoding="utf-8"))
    for row in history:
        epoch = int(row["epoch"])
        # Prefer structured, full-precision training losses where recorded.
        records[epoch]["training_loss"] = float(row["training_loss"])
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    epochs = np.arange(1, 12)

    # 1. Training loss, log values for epochs 1–6 and exact history values for 7–11.
    fig, ax = plt.subplots(figsize=(6.6, 4.0), constrained_layout=True)
    ax.plot(epochs, [records[e]["training_loss"] for e in epochs], marker="o", ms=5,
            lw=2, color="#245b8f", label="Training loss")
    ax.set(title="SNUNet-CD training loss", xlabel="Epoch", ylabel="Training loss")
    ax.set_xticks(epochs)
    ax.set_xlim(0.7, 11.3)
    ax.legend(frameon=False, loc="upper right")
    incomplete_note(ax)
    save(fig, "fig1_training_loss")

    # 2. Epoch-wise validation F1 and IoU, precisely as recorded in the epoch log.
    fig, ax = plt.subplots(figsize=(6.6, 4.0), constrained_layout=True)
    ax.plot(epochs, [records[e]["validation_f1"] for e in epochs], marker="o", ms=5,
            lw=2, color="#167a72", label="Validation F1-score")
    ax.plot(epochs, [records[e]["validation_iou"] for e in epochs], marker="s", ms=4.5,
            lw=2, color="#c87524", label="Validation IoU")
    ax.set(title="SNUNet-CD validation performance", xlabel="Epoch", ylabel="Validation metric")
    ax.set_xticks(epochs)
    ax.set_xlim(0.7, 11.3)
    ax.set_ylim(0, 1)
    ax.legend(frameon=False, loc="lower right")
    incomplete_note(ax)
    save(fig, "fig2_validation_f1_iou")

    # 3. Precision and recall exist in structured validation history for epochs 7–11 only.
    hist_epochs = [int(row["epoch"]) for row in history]
    fig, ax = plt.subplots(figsize=(6.6, 4.0), constrained_layout=True)
    ax.plot(hist_epochs, [row["validation"]["precision"] for row in history], marker="o",
            ms=5, lw=2, color="#6b5ca5", label="Validation precision")
    ax.plot(hist_epochs, [row["validation"]["recall"] for row in history], marker="s",
            ms=4.5, lw=2, color="#b44b5a", label="Validation recall")
    ax.set(title="SNUNet-CD validation precision and recall", xlabel="Epoch",
           ylabel="Validation metric")
    ax.set_xticks(hist_epochs)
    ax.set_xlim(6.6, 11.4)
    ax.set_ylim(0, 1)
    ax.legend(frameon=False, loc="best")
    incomplete_note(ax)
    save(fig, "fig3_validation_precision_recall")

    # 4. Best-epoch validation confusion matrix. Rows=true class, columns=predicted class.
    best_epoch = int(report["best_epoch"])
    metrics = report["best_validation_metrics"]
    cm = np.array([[metrics["true_negatives"], metrics["false_positives"]],
                   [metrics["false_negatives"], metrics["true_positives"]]], dtype=np.int64)
    if best_epoch != 10:
        raise ValueError(f"Expected report best epoch 10; found {best_epoch}")
    fig, ax = plt.subplots(figsize=(6.4, 4.8), constrained_layout=True)
    row_pct = cm / cm.sum(axis=1, keepdims=True) * 100
    im = ax.imshow(row_pct, cmap="Blues", norm=Normalize(0, 100), aspect="auto")
    labels = [["TN", "FP"], ["FN", "TP"]]
    for i in range(2):
        for j in range(2):
            color = "white" if row_pct[i, j] > 55 else "#152331"
            ax.text(j, i, f"{labels[i][j]}\n{cm[i,j]:,}\n({row_pct[i,j]:.2f}%)",
                    ha="center", va="center", color=color, fontsize=10, fontweight="semibold")
    ax.set_xticks([0, 1], ["No change", "Change"])
    ax.set_yticks([0, 1], ["No change", "Change"])
    ax.set_xlabel("Predicted class")
    ax.set_ylabel("Ground-truth class")
    ax.set_title("Validation confusion matrix — best epoch 10\n(rows normalized; cells show actual counts)")
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Within-class percentage (%)")
    ax.text(0.5, -0.22, "Validation metrics · threshold 0.30 · run incomplete (11/40 epochs)",
            transform=ax.transAxes, ha="center", va="top", fontsize=8, color="#555555")
    save(fig, "fig4_validation_confusion_matrix_epoch10")

    # 5. Dataset pair counts. Test split is shown as available, not evaluated.
    counts = [int(manifest["training_pair_count"]), int(manifest["validation_pair_count"]), 348]
    categories = ["Training", "Validation", "Official test\n(unevaluated)"]
    colors = ["#245b8f", "#4c9a8a", "#9a9a9a"]
    fig, ax = plt.subplots(figsize=(6.8, 4.2), constrained_layout=True)
    bars = ax.bar(categories, counts, color=colors, width=0.62, edgecolor="white", linewidth=0.8)
    ax.set_title("LEVIR-CD+ dataset pair distribution")
    ax.set_ylabel("Image pairs")
    ax.set_ylim(0, max(counts) * 1.22)
    ax.grid(axis="x", visible=False)
    ax.bar_label(bars, labels=[f"{v:,}" for v in counts], padding=4, fontsize=10, fontweight="bold")
    ax.text(2, counts[2] * 0.52, "Not evaluated", ha="center", va="center", fontsize=9,
            color="white", fontweight="bold")
    ax.text(0.01, 0.98, "Train/validation: seed-42 manifest split of 637 training pairs",
            transform=ax.transAxes, ha="left", va="top", fontsize=8, color="#555555")
    save(fig, "fig5_dataset_distribution")

    print("Generated figures from:")
    for path in (LOG, HISTORY, REPORT, MANIFEST):
        print(f"  {path.relative_to(ROOT)}")
    print("Training loss (epochs 1–11):", [records[e]["training_loss"] for e in epochs])
    print("Validation F1 (epochs 1–11):", [records[e]["validation_f1"] for e in epochs])
    print("Validation IoU (epochs 1–11):", [records[e]["validation_iou"] for e in epochs])
    print("Validation precision (epochs 7–11):", [row["validation"]["precision"] for row in history])
    print("Validation recall (epochs 7–11):", [row["validation"]["recall"] for row in history])
    print("Epoch-10 confusion counts [[TN, FP], [FN, TP]]:", cm.tolist())
    print("Dataset pairs [training, validation, official test unevaluated]:", counts)
    print("Missing data: validation loss absent; precision/recall absent for epochs 1–6; run only recorded through epoch 11 of 40.")


if __name__ == "__main__":
    main()
