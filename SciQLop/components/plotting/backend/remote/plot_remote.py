"""Build a SciQLopPlots remote-backed graph bound to a worker channel."""
from __future__ import annotations

import itertools

from SciQLopPlots import SciQLopPlot, ParameterType, PlotType
from .channel import RemoteChannel
from .registry import remote_registry

_channel_ids = itertools.count(1)


def _new_plot(target, plot_type: PlotType):
    if isinstance(target, SciQLopPlot):
        return target
    return target.create_plot(plot_type=plot_type)


def plot_remote(target, node, provider, product: list, *, plot_type: PlotType = PlotType.TimeSeries):
    """Create a remote-backed graph for *product* on *target*.

    Returns (plot, graph).  The graph's destroyed signal disposes the channel
    so the worker is released when the graph is removed.  The channel object
    is captured in the lambda — not the graph — which is safe per the
    Qt lifetime rules: disposed never touches the dying widget.
    """
    reg = remote_registry()
    plot = _new_plot(target, plot_type)
    ptype = node.parameter_type()
    if ptype == ParameterType.Spectrogram:
        graph = plot.add_remote_color_map(node.display_name())
    else:
        labels = list(provider.labels(node))
        graph = plot.add_remote_line_graph(labels=labels)
    pipeline = graph.remote_channel()
    worker = reg.worker_for(product)
    channel = RemoteChannel(pipeline=pipeline, channel_id=next(_channel_ids),
                            transport=worker)
    graph._remote_channel = channel
    worker.register_channel(channel)
    blob, arity = reg.spec_for(product)
    worker.install(channel.channel_id, blob, arity)
    pipeline.data_requested.connect(channel.on_data_requested)
    graph.destroyed.connect(lambda *_: channel.dispose())
    return plot, graph
