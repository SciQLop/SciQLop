"""SciQLop DSP user API. Two-layer facade over SciQLopPlots.dsp.

Layer 1 (this package's public surface): SpeasyVariable-aware wrappers.
Layer 2 (_arrays.py): thin numpy pass-through.

All public functions are marked @experimental_api().
"""
from . import _arrays as arrays  # noqa: F401  (re-exported below in Task 14)
