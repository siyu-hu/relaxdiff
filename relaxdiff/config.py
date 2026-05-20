"""Thresholds and tunable parameters."""

import os
from dataclasses import dataclass, field


@dataclass
class Thresholds:
    displacement_warn: float = 0.5      # Å
    displacement_alert: float = 2.0     # Å
    runaway_zscore: float = 3.0
    volume_warn: float = 0.10           # fraction
    volume_alert: float = 0.15
    shear_warn: float = 0.05            # off-diagonal strain
    bond_length_change_warn: float = 0.15  # fraction
    symprec_scan: tuple = (1e-3, 1e-2, 5e-2, 1e-1, 2e-1)
    default_symprec: float = 0.1


@dataclass
class LLMConfig:
    """LLM provider config. Defaults to DeepSeek's OpenAI-compatible endpoint.

    Both `model` and `base_url` honor the `RELAXDIFF_LLM_MODEL` and
    `RELAXDIFF_LLM_BASE_URL` environment variables when set, so you can swap
    providers without editing code.
    """
    model: str = field(
        default_factory=lambda: os.environ.get("RELAXDIFF_LLM_MODEL", "deepseek-chat")
    )
    base_url: str = field(
        default_factory=lambda: os.environ.get(
            "RELAXDIFF_LLM_BASE_URL", "https://api.deepseek.com"
        )
    )
    api_key_env: str = "DEEPSEEK_API_KEY"
    max_tokens: int = 1024
    temperature: float = 0.4
    enabled: bool = True


@dataclass
class Config:
    thresholds: Thresholds = field(default_factory=Thresholds)
    llm: LLMConfig = field(default_factory=LLMConfig)


DEFAULT = Config()
