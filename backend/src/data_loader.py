"""Filename-based loading and validation for a LEVIR-CD split."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import numpy as np
from PIL import Image, UnidentifiedImageError

SUPPORTED_EXTENSIONS = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}
FOLDER_NAMES = ("A", "B", "label")


class DatasetError(Exception):
    """Raised when the dataset folders or image files cannot be used."""


@dataclass(frozen=True)
class ImagePair:
    """One earlier image, later image, and reference mask with the same filename."""

    name: str
    earlier_path: Path
    later_path: Path
    label_path: Path


@dataclass(frozen=True)
class DatasetInspection:
    """Validated dataset pairs and a report of missing or unusable files."""

    root: Path
    folders_present: dict[str, bool]
    file_counts: dict[str, int]
    valid_pairs: tuple[ImagePair, ...]
    missing_later: tuple[str, ...]
    missing_labels: tuple[str, ...]
    unpaired_later: tuple[str, ...]
    unpaired_labels: tuple[str, ...]
    errors: tuple[str, ...]


def _natural_key(value: str) -> list[object]:
    return [int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", value)]


def _image_files(folder: Path) -> dict[str, Path]:
    return {
        item.name: item
        for item in folder.iterdir()
        if item.is_file() and item.suffix.casefold() in SUPPORTED_EXTENSIONS
    }


def _validate_image_pair(pair: ImagePair) -> str | None:
    dimensions: dict[str, tuple[int, int]] = {}
    for label, path in (
        ("A", pair.earlier_path),
        ("B", pair.later_path),
        ("label", pair.label_path),
    ):
        try:
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                dimensions[label] = image.size
        except (OSError, UnidentifiedImageError, ValueError) as exc:
            return f"{pair.name}: cannot read {label} image ({path.name}): {exc}"

    if len(set(dimensions.values())) != 1:
        return f"{pair.name}: image dimensions do not match (A={dimensions['A']}, B={dimensions['B']}, label={dimensions['label']})"
    return None


def inspect_dataset(root: str | Path) -> DatasetInspection:
    """Match images by exact filename, validate readability, and report gaps."""
    dataset_root = Path(root)
    folders = {name: dataset_root / name for name in FOLDER_NAMES}
    folders_present = {name: folder.is_dir() for name, folder in folders.items()}
    missing_folders = [name for name, exists in folders_present.items() if not exists]
    if missing_folders:
        raise DatasetError(
            f"Dataset folders are missing under {dataset_root}: {', '.join(missing_folders)}"
        )

    files = {name: _image_files(folder) for name, folder in folders.items()}
    earlier_names = set(files["A"])
    later_names = set(files["B"])
    label_names = set(files["label"])
    shared_names = earlier_names & later_names & label_names

    missing_later = earlier_names - later_names
    missing_labels = earlier_names - label_names
    valid_pairs: list[ImagePair] = []
    errors: list[str] = []
    for name in sorted(shared_names, key=_natural_key):
        pair = ImagePair(
            name=name,
            earlier_path=files["A"][name],
            later_path=files["B"][name],
            label_path=files["label"][name],
        )
        error = _validate_image_pair(pair)
        if error:
            errors.append(error)
        else:
            valid_pairs.append(pair)

    return DatasetInspection(
        root=dataset_root,
        folders_present=folders_present,
        file_counts={name: len(files[name]) for name in FOLDER_NAMES},
        valid_pairs=tuple(valid_pairs),
        missing_later=tuple(sorted(missing_later, key=_natural_key)),
        missing_labels=tuple(sorted(missing_labels, key=_natural_key)),
        unpaired_later=tuple(sorted(later_names - earlier_names, key=_natural_key)),
        unpaired_labels=tuple(sorted(label_names - earlier_names, key=_natural_key)),
        errors=tuple(errors),
    )


def load_pair(pair: ImagePair) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Load RGB earlier/later images and a boolean reference change mask."""
    with Image.open(pair.earlier_path) as image:
        earlier = np.asarray(image.convert("RGB"))
    with Image.open(pair.later_path) as image:
        later = np.asarray(image.convert("RGB"))
    with Image.open(pair.label_path) as image:
        label = np.asarray(image.convert("L")) > 0

    if earlier.shape != later.shape or earlier.shape[:2] != label.shape:
        raise DatasetError(
            f"{pair.name}: image dimensions changed after loading "
            f"(A={earlier.shape}, B={later.shape}, label={label.shape})"
        )
    return earlier, later, label
