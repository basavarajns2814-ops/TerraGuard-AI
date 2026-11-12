import numpy as np
import pytest

from app.services.change_detection.service import ChangeDetectionService


def test_invalid_pixels_are_excluded_from_mask_and_probability_map():
    binary = np.array([[255, 255], [0, 255]], dtype=np.uint8)
    probabilities = np.array([[0.9, 0.8], [0.1, 0.7]], dtype=np.float32)
    valid = np.array([[True, False], [True, True]])

    masked_binary, masked_probabilities = ChangeDetectionService.apply_valid_data_mask(
        binary, probabilities, valid
    )

    np.testing.assert_array_equal(masked_binary, [[255, 0], [0, 255]])
    np.testing.assert_allclose(masked_probabilities, [[0.9, 0.0], [0.1, 0.7]])


def test_valid_data_mask_rejects_mismatched_dimensions():
    with pytest.raises(ValueError, match="dimensions must match"):
        ChangeDetectionService.apply_valid_data_mask(
            np.zeros((2, 2), dtype=np.uint8), None, np.ones((3, 2), dtype=bool)
        )
