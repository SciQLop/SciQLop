from typing import ClassVar, Literal
from pydantic import Field, model_validator
from .entry import ConfigEntry, SettingsCategory


class PlotBackendSettings(ConfigEntry):
    category: ClassVar[str] = SettingsCategory.APPLICATION
    subcategory: ClassVar[str] = "Plotting"

    default_speasy_backend: Literal["matplotlib", "sciqlop"] = Field(
        default="matplotlib",
        description="Library used when a Speasy snippet plots outside "
                    "SciQLop.")
    default_zoom_limit: Literal["1h", "1d", "1w", "1y", "Unlimited"] = Field(
        default="1d",
        description="How far new panels let you zoom out on the time axis.")

    graph_autoscale_percentile_low: float = Field(
        default=0.0, ge=0.0, le=100.0,
        description="Percentile of the data used as the lower bound when a "
                    "plot auto-scales its Y axis; keeps outliers from "
                    "flattening the curve.")
    graph_autoscale_percentile_high: float = Field(
        default=100.0, ge=0.0, le=100.0,
        description="Percentile of the data used as the upper bound when a "
                    "plot auto-scales its Y axis; keeps outliers from "
                    "flattening the curve.")
    colormap_autoscale_percentile_low: float = Field(
        default=2.0, ge=0.0, le=100.0,
        description="Percentile of the data used as the lower bound when a "
                    "spectrogram auto-scales its color scale; keeps "
                    "outliers from flattening the curve.")
    colormap_autoscale_percentile_high: float = Field(
        default=98.0, ge=0.0, le=100.0,
        description="Percentile of the data used as the upper bound when a "
                    "spectrogram auto-scales its color scale; keeps "
                    "outliers from flattening the curve.")

    @model_validator(mode="after")
    def _percentile_low_below_high(self) -> "PlotBackendSettings":
        if self.graph_autoscale_percentile_low >= self.graph_autoscale_percentile_high:
            raise ValueError("graph_autoscale_percentile_low must be < high")
        if self.colormap_autoscale_percentile_low >= self.colormap_autoscale_percentile_high:
            raise ValueError("colormap_autoscale_percentile_low must be < high")
        return self
