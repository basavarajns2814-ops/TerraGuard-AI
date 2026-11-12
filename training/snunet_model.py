"""SNUNet-CD architecture for LEVIR-CD+ change detection.

This implementation uses shared-weight Siamese encoders, dense nested U-Net++
skips, and squeeze-excitation channel attention. It is independent from
training/model.py so EXP-01 artifacts remain unchanged.
"""

from __future__ import annotations

import torch
from torch import Tensor, nn
from torch.nn import functional as F


class ChannelAttention(nn.Module):
    """Lightweight squeeze-and-excitation channel attention (ECAM)."""

    def __init__(self, channels: int, reduction: int = 16) -> None:
        super().__init__()
        hidden = max(4, channels // reduction)
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.mlp = nn.Sequential(
            nn.Conv2d(channels, hidden, kernel_size=1, bias=True),
            nn.ReLU(inplace=True),
            nn.Conv2d(hidden, channels, kernel_size=1, bias=True),
            nn.Sigmoid(),
        )

    def forward(self, value: Tensor) -> Tensor:
        return value * self.mlp(self.pool(value))


class ConvBlock(nn.Module):
    def __init__(self, in_channels: int, out_channels: int) -> None:
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, value: Tensor) -> Tensor:
        return self.block(value)


class SiameseEncoder(nn.Module):
    """Four-level shared-weight convolution encoder."""

    def __init__(self, base_width: int = 32) -> None:
        super().__init__()
        widths = (base_width, base_width * 2, base_width * 4, base_width * 8)
        self.input_block = ConvBlock(3, widths[0])
        self.down1 = ConvBlock(widths[0], widths[1])
        self.down2 = ConvBlock(widths[1], widths[2])
        self.down3 = ConvBlock(widths[2], widths[3])
        self.pool = nn.MaxPool2d(2, 2)

    def forward(self, image: Tensor) -> tuple[Tensor, Tensor, Tensor, Tensor]:
        x0 = self.input_block(image)
        x1 = self.down1(self.pool(x0))
        x2 = self.down2(self.pool(x1))
        x3 = self.down3(self.pool(x2))
        return x0, x1, x2, x3


class SNUNetCD(nn.Module):
    """SNUNet-CD with Siamese encoding, nested dense skips, and ECAM attention."""

    def __init__(self, base_width: int = 32, pretrained: bool = False) -> None:
        super().__init__()
        if pretrained:
            raise ValueError("pretrained is not supported for this self-contained SNUNet-CD implementation.")
        self.base_width = int(base_width)
        if self.base_width <= 0:
            raise ValueError("base_width must be positive.")

        widths = (base_width, base_width * 2, base_width * 4, base_width * 8)
        self.encoder = SiameseEncoder(base_width)
        self.fusions = nn.ModuleList()
        self.fusion_attentions = nn.ModuleList()
        for width in widths:
            self.fusions.append(ConvBlock(width * 3, width))
            self.fusion_attentions.append(ChannelAttention(width))

        self.bottom_fusion = ConvBlock(widths[-1] * 3, widths[-1])
        self.bottom_attention = ChannelAttention(widths[-1])

        # Dense nested decoder nodes. For row i, column j combines every same-row
        # node to its left with the upsampled node from row i+1, column j-1.
        self.nodes = nn.ModuleDict()
        for i in range(4):
            for j in range(1, 4 - i):
                local_inputs = j * widths[i] + widths[i + 1]
                self.nodes[f"x{i}_{j}"] = ConvBlock(local_inputs, widths[i])
        self.node_attentions = nn.ModuleDict()
        for i in range(4):
            for j in range(1, 4 - i):
                self.node_attentions[f"x{i}_{j}"] = ChannelAttention(widths[i])

        self.output_head = nn.Sequential(
            nn.Conv2d(widths[0] * 4, widths[0], kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(widths[0]),
            nn.ReLU(inplace=True),
            nn.Conv2d(widths[0], 1, kernel_size=1),
        )

        self._initialize()

    def _initialize(self) -> None:
        for module in self.modules():
            if isinstance(module, nn.Conv2d):
                nn.init.kaiming_normal_(module.weight, mode="fan_out", nonlinearity="relu")
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
            elif isinstance(module, nn.BatchNorm2d):
                nn.init.ones_(module.weight)
                nn.init.zeros_(module.bias)

    @staticmethod
    def _fuse_siamese(a: Tensor, b: Tensor) -> Tensor:
        return torch.cat((a, b, torch.abs(a - b)), dim=1)

    def forward(self, image_a: Tensor, image_b: Tensor) -> Tensor:
        if image_a.ndim != 4 or image_b.ndim != 4:
            raise ValueError("image_a and image_b must be 4D tensors [B, 3, H, W].")
        if image_a.shape != image_b.shape:
            raise ValueError("image_a and image_b must have identical shapes.")
        if image_a.shape[1] != 3:
            raise ValueError("Both inputs must have exactly three RGB channels.")
        input_size = image_a.shape[-2:]

        enc_a = self.encoder(image_a)
        enc_b = self.encoder(image_b)
        fused = []
        for index, (a, b) in enumerate(zip(enc_a, enc_b)):
            value = torch.cat((a, b, torch.abs(a - b)), dim=1)
            value = self.fusions[index](value)
            value = self.fusion_attentions[index](value)
            fused.append(value)

        bottom = self._fuse_siamese(enc_a[-1], enc_b[-1])
        bottom = self.bottom_attention(self.bottom_fusion(bottom))

        # The deepest node is the dedicated Siamese bottleneck fusion.
        fused[-1] = bottom

        # Nested dense skip nodes: x[i][j] with x[i][0] = fused encoder level i.
        x: list[list[Tensor | None]] = [[None for _ in range(4)] for _ in range(4)]
        for i in range(4):
            x[i][0] = fused[i]

        for j in range(1, 4):
            for i in range(4 - j):
                below = x[i + 1][j - 1]
                if below is None:
                    raise RuntimeError("SNUNet nested decoder graph is incomplete.")
                below = F.interpolate(below, size=x[i][0].shape[-2:], mode="bilinear", align_corners=False)
                inputs = torch.cat([*(node for node in x[i][:j] if node is not None), below], dim=1)
                node = self.nodes[f"x{i}_{j}"](inputs)
                node = self.node_attentions[f"x{i}_{j}"](node)
                x[i][j] = node

        final_features = torch.cat((x[0][1], x[0][2], x[0][3], fused[0]), dim=1)
        logits = self.output_head(final_features)
        logits = F.interpolate(logits, size=input_size, mode="bilinear", align_corners=False)
        return logits


def count_parameters(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
