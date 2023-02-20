from .base import model
from SciQLop.backend.pipelines_model.base.pipeline_model_item import PipelineModelItem


class TimeSyncPanel(PipelineModelItem):
    def __init__(self, name: str):
        super(TimeSyncPanel, self).__init__(name, None)
        model.add_add_panel(self)
