"""Deterministic trading core: strategy, risk, execution, data, ledger.

Nothing in `core` may call an LLM. Every decision made here must be
reproducible and unit-testable, because this is the layer that moves money.
"""
