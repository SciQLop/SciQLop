from typing import ClassVar

from pydantic import Field

from SciQLop.components.settings.backend.entry import ConfigEntry, SettingsCategory


class ProfilingSettings(ConfigEntry):
    category: ClassVar[str] = SettingsCategory.APPLICATION
    subcategory: ClassVar[str] = "Profiling"

    # Sampler (sampler.py). Ships default-off: a real measurement (idle-ish
    # dev process, ~10-15 threads, 200ms interval) showed unmeasurably small
    # CPU cost, but that hasn't been re-measured at real SciQLop's thread
    # count/stack depth -- flip on once that number exists.
    sampler_enabled: bool = Field(
        default=False,
        description="Continuously sample all threads' stacks into a ring "
                    "buffer, so a stall dump can show what was running in "
                    "the seconds before it happened.")
    sample_interval_ms: int = Field(
        default=200, ge=20, le=5000,
        description="Milliseconds between two stack samples.")
    sample_buffer_seconds: int = Field(
        default=60, ge=5, le=600,
        description="How much sampling history to keep before older samples "
                    "are evicted.")

    # Watchdog (watchdog.py).
    watchdog_enabled: bool = Field(
        default=True,
        description="Write a diagnostic dump when the interface stops "
                    "responding.")
    watchdog_stall_threshold_s: float = Field(
        default=3.0, ge=0.5, le=60.0,
        description="Main-thread unresponsive for longer than this silently "
                    "triggers a diagnostic dump. The resampler and remote "
                    "worker are already off the main thread by design, so "
                    "this is already anomalous, not a normal big-fetch case.")
    watchdog_severe_threshold_s: float = Field(
        default=10.0, ge=0.5, le=120.0,
        description="Additionally surfaced (not just silently dumped) past "
                    "this threshold.")
    watchdog_cooldown_s: float = Field(
        default=30.0, ge=1.0, le=600.0,
        description="Minimum time between dumps while still stalled.")
    watchdog_max_dumps_per_session: int = Field(
        default=20, ge=1, le=1000,
        description="Stop dumping after this many dumps in one session.")
