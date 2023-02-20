from SciQLop.backend.pipelines_model.base.pipeline_model_item import PipelineModelItem


class Plot(PipelineModelItem):
    def __init__(self, name: str, parent):
        super(Plot, self).__init__(name, parent)
