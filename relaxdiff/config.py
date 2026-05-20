"""Thresholds and tunable parameters."""

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
    model: str = "claude-haiku-4-5-20251001"
    max_tokens: int = 1024
    enabled: bool = True


@dataclass
class Config:
    thresholds: Thresholds = field(default_factory=Thresholds)
    llm: LLMConfig = field(default_factory=LLMConfig)


DEFAULT = Config()
