"""Re-export the sleeve spec model for firm-layer callers."""

from core.strategy.sleeve_spec import (
    CHANNELS,
    STRETCHES,
    TEMPLATES,
    TRENDS,
    SleeveSpec,
)

__all__ = ["CHANNELS", "STRETCHES", "TEMPLATES", "TRENDS", "SleeveSpec"]
