import sys
import os
import copy

if not hasattr(sys, 'argv'):
    sys.argv = ['']
current_script_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(current_script_path)
import amda
import pytestamda
import pysciqlopcore
import sciqlopqt

import datetime
import random
import string
import jsonpickle
import argparse

class Variable:
    class Range:
        def __init__(self, start, stop):
            self.start = start
            self.stop = stop

    def __init__(self, name, t_start, t_stop):
        self.name = name
        self.range = Variable.Range(t_start, t_stop)


class OperationCtx:
    def __init__(self, prev_ctx=None):
        if prev_ctx is None:
            self.t_start = datetime.datetime(2012, 10, 20, 8, 10, 00)
            self.t_stop = datetime.datetime(2012, 10, 20, 12, 0, 0)
            self.variables = dict()
            self.sync_group = set()
        else:
            self.t_start = copy.deepcopy(prev_ctx.t_start)
            self.t_stop = copy.deepcopy(prev_ctx.t_stop)
            self.variables = copy.deepcopy(prev_ctx.variables)
            self.sync_group = copy.deepcopy(prev_ctx.sync_group)


__variables__ = dict()

__variables_in_sync__ = set()

__OPS__ = {}
__WEIGHTS__ = {}

sync_group = sciqlopqt.QUuid()
pytestamda.VariableController.addSynchronizationGroup(sync_group)


def register(weight):
    def register_(cls):
        __OPS__[cls.__name__] = cls()
        __WEIGHTS__[cls.__name__] = weight
        return cls

    return register_


def random_var(ctx):
    if len(ctx.variables):
        return random.choice(list(ctx.variables.keys()))
    else:
        return None


@register(2)
class CreateVar:
    @staticmethod
    def prepare(ctx, *args, **kwargs):
        new_random_name = ''.join(random.choices(string.ascii_letters + string.digits, k=random.randint(1, 40)))
        ctx.variables[new_random_name] = Variable(new_random_name, ctx.t_start, ctx.t_stop)
        return {"var_name": new_random_name}

    @staticmethod
    def do(var_name, *args, **kwargs):
        __variables__[var_name] = pytestamda.VariableController.createVariable(var_name,
                                                                               pytestamda.amda_provider())


@register(1)
class DeleteVar:
    @staticmethod
    def prepare(ctx, *args, **kwargs):
        var_name = random_var(ctx)
        if var_name:
            ctx.variables.pop(var_name)
            ctx.sync_group.discard(var_name)
        return {"var_name": var_name}

    @staticmethod
    def do(var_name, *args, **kwargs):
        if var_name:
            variable = __variables__.pop(var_name)
            pytestamda.VariableController.deleteVariable(variable)


class Zoom:
    @staticmethod
    def _compute_zoom_ranges(factor, variable):
        delta = variable.range.stop - variable.range.start
        center = variable.range.start + (delta / 2)
        new_delta = delta * factor
        t_start = center - new_delta / 2
        t_stop = center + new_delta / 2
        return t_start, t_stop

    @staticmethod
    def _zoom(factor, var_name, ctx):
        var_list = ctx.sync_group if var_name in ctx.sync_group else [var_name]
        for var_name in var_list:
            variable = ctx.variables[var_name]
            t_start, t_stop = Zoom._compute_zoom_ranges(variable=variable, factor=factor)
            ctx.variables[var_name].range.start = t_start
            ctx.variables[var_name].range.stop = t_stop

    @staticmethod
    def prepare(ctx, min, max):
        var_name = random_var(ctx)
        factor = random.uniform(min, max)
        if var_name:
            Zoom._zoom(factor, var_name, ctx)
        return {"var_name": var_name, "factor": factor}

    @staticmethod
    def do(var_name, factor):
        variable = __variables__[var_name]
        t_start, t_stop = Zoom._compute_zoom_ranges(variable = variable, factor = factor)
        sync = True if var_name in __variables_in_sync__ else False
        pytestamda.VariableController.update_range(variable, pytestamda.SqpRange(t_start, t_stop), sync)


@register(10)
class ZoomIn:
    @staticmethod
    def prepare(ctx, *args, **kwargs):
        return Zoom.prepare(ctx, min=1, max=2)

    @staticmethod
    def do(var_name, factor, *args, **kwargs):
        if var_name:
            Zoom.do(var_name, factor)


@register(10)
class ZoomOut:
    @staticmethod
    def prepare(ctx, *args, **kwargs):
        return Zoom.prepare(ctx, min=.1, max=1)

    @staticmethod
    def do(var_name, factor, *args, **kwargs):
        if var_name:
            Zoom.do(var_name, factor)


@register(10)
class Shift:
    @staticmethod
    def _compute_range(variable, direction, factor):
        delta = variable.range.stop - variable.range.start
        offset = delta * factor * direction
        return variable.range.start + offset, variable.range.stop + offset

    @staticmethod
    def prepare(ctx, *args, **kwargs):
        var_name = random_var(ctx)
        direction = random.choice([1, -1])
        factor = random.random()
        if var_name:
            var_list = ctx.sync_group if var_name in ctx.sync_group else [var_name]
            for var_name in var_list:
                variable = ctx.variables[var_name]
                delta = variable.range.stop - variable.range.start
                offset = delta * factor * direction
                variable.range.start , variable.range.stop = Shift._compute_range(variable, direction, factor)
        return {"var_name": var_name, "direction": direction, "factor": factor}

    @staticmethod
    def do(var_name, direction, factor, *args, **kwargs):
        if var_name:
            variable = __variables__[var_name]
            t_start, t_stop = Shift._compute_range(variable, direction, factor)
            sync = True if var_name in __variables_in_sync__ else False
            pytestamda.VariableController.update_range(variable, pytestamda.SqpRange(t_start, t_stop), sync)


@register(3)
class WaitForDl:
    @staticmethod
    def prepare(ctx, *args, **kwargs):
        return {}

    @staticmethod
    def do(*args, **kwargs):
        pytestamda.VariableController.wait_for_downloads()


@register(2)
class SyncVar:
    @staticmethod
    def prepare(ctx, *args, **kwargs):
        var_name = random_var(ctx)
        if var_name:
            ctx.sync_group.add(var_name)
        return {"var_name": var_name}

    @staticmethod
    def do(var_name, *args, **kwargs):
        if var_name:
            pytestamda.VariableController.synchronizeVar(__variables__[var_name], sync_group)
            __variables_in_sync__.add(var_name)


@register(2)
class DeSyncVar:
    @staticmethod
    def prepare(ctx, *args, **kwargs):
        var_name = random_var(ctx)
        if var_name:
            ctx.sync_group.discard(var_name)
        return {"var_name": var_name}

    @staticmethod
    def do(var_name, *args, **kwargs):
        if var_name:
            pytestamda.VariableController.deSynchronizeVar(__variables__[var_name], sync_group)
            __variables_in_sync__.discard(var_name)


#parser = argparse.ArgumentParser()
#parser.add_argument("-r", "--reload", help="reload")
#cli_args = parser.parse_args()


def run_scenario(args,ops):
    t_start, t_stop = datetime.datetime(2012, 10, 20, 8, 10, 00), datetime.datetime(2012, 10, 20, 12, 0, 0)
    pytestamda.TimeController.setTime(pytestamda.SqpRange(t_start, t_stop))

    for op_name,arg in zip(ops,args):
        operation = __OPS__[op_name]
        operation.do(**arg)


def build_scenario(name, steps=100):
    context_stack = [OperationCtx()]
    ops = [CreateVar.__name__]  # start with one variable minimum
    ops += random.choices(list(__OPS__.keys()), weights=list(__WEIGHTS__.values()), k=steps)
    ops.append(SyncVar.__name__)
    for op_name in ops:
        ctx = OperationCtx(context_stack[-1])
        operation = __OPS__[op_name]
        args.append(operation.prepare(ctx))
        context_stack.append(ctx)
    os.makedirs(name)
    js = jsonpickle.encode({"args": args, "context_stack": context_stack, "operations": ops})
    with open(name+"/input.json", "w") as file:
        file.write(js)
    return ops, args, context_stack


def load_scenario(name):
    with open(name+"/input.json", "r") as file:
        js = file.read()
    data = jsonpickle.decode(js)
    return data["operations"], data["args"], data["context_stack"]


if __name__ == '__main__':
    scenario = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    #ops,args, context_stack = build_scenario(scenario, 300)
    #print("Generated scenario {}".format(scenario))
    name = "EuI9qFMLZJ4k7vf8seTww8Z4wGBpspd8"
    ops, args, context_stack = load_scenario(name)
    syncs = [WaitForDl.__name__]*len(ops)
    syncs_args = [{}]*len(ops)
    ops2 = [op for pair in zip(ops,syncs) for op in pair]
    args2 = [arg for pair in zip(args,syncs_args) for arg in pair]
    run_scenario(args=args2, ops=ops2)
