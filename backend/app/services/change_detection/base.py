from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple
import numpy as np

class ChangeDetectionStrategy(ABC):
    @abstractmethod
    def detect(
        self,
        historical_img: np.ndarray,
        recent_img: np.ndarray,
        parameters: Dict[str, Any]
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Executes change detection strategy.
        Returns:
            binary_mask: 2D uint8 numpy array (0 = no change, 255 = detected change candidate)
            metadata: dictionary of metrics, algorithm version, and details
        """
        pass
