import traceback
import os
from datetime import datetime, timedelta, timezone
from SciQLopBindings import PyDataProvider, Product, VectorTimeSerie, ScalarTimeSerie, DataSeriesType
import numpy as np
import requests
import copy
import speasy as spz


def amda_make_scalar(var=None):
    if var is None:
        return (((np.array([]), np.array([])), np.array([])), DataSeriesType.SCALAR)
    else:
        return (((var.time, np.array([])), var.data), DataSeriesType.SCALAR)


def amda_make_vector(var=None):
    if var is None:
        return (((np.array([]), np.array([])), np.array([])), DataSeriesType.VECTOR)
    else:
        return (((var.time, np.array([])), var.data), DataSeriesType.VECTOR)


def amda_make_multi_comp(var=None):
    if var is None:
        return (((np.array([]), np.array([])), np.array([])), DataSeriesType.MULTICOMPONENT)
    else:
        return (((var.time, np.array([])), var.data), DataSeriesType.MULTICOMPONENT)


def amda_make_spectro(var=None):
    if var is None:
        return (((np.array([]), np.array([])), np.array([])), DataSeriesType.SPECTROGRAM)
    else:
        min_sampling = float(var.meta.get("DATASET_MIN_SAMPLING", "nan"))
        max_sampling = float(var.meta.get("DATASET_MAX_SAMPLING", "nan"))
        if var.y is None and len(var.data):
            var.y = np.logspace(1, 3, var.data.shape[1])[::-1]
        return (((var.time, var.y), var.data), DataSeriesType.SPECTROGRAM)
        #return pysciqlopcore.SpectrogramTimeSerie(var.time,y,var.data,min_sampling,max_sampling,True)


def amda_get_sample(metadata, start, stop):
    ts_type = amda_make_scalar
    try:
        param_id = None
        for key, value in metadata:
            if key == 'xml:id':
                param_id = value
            elif key == 'type':
                if value == 'vector':
                    ts_type = amda_make_vector
                elif value == 'multicomponent':
                    ts_type = amda_make_multi_comp
                elif value == 'spectrogram':
                    ts_type = amda_make_spectro
        tstart = datetime.fromtimestamp(start, tz=timezone.utc)
        tend = datetime.fromtimestamp(stop, tz=timezone.utc)
        var = spz.amda.get_parameter(start_time=tstart, stop_time=tend, parameter_id=param_id, method="REST")
        return ts_type(var)
    except Exception as e:
        print(traceback.format_exc())
        print("Error in amda.py ", str(e))
        return ts_type()


class AmdaProvider(PyDataProvider):
    def __init__(self):
        super(AmdaProvider, self).__init__()
        '''if len(amda.component) is 0:
            amda.update_inventory()
        parameters = copy.deepcopy(spz.inventory.flat_inventories.amda.parameter)
        for name, component in spz.inventory.flat_inventories.amda.components.items():
            if 'components' in parameters[component['parameter']]:
                parameters[component['parameter']]['components'].append(component)
            else:
                parameters[component['parameter']]['components']=[component]

        products = []
        for key, parameter in parameters.items():
            mission_name = amda.mission[parameter['mission']]['name']
            observatory_name = parameter.get('observatory','')
            if observatory_name != '':
                observatory_name = amda.observatory[observatory_name]['name']
            instrument_name = amda.instrument[parameter['instrument']]['name']
            dataset_name = amda.dataset[parameter['dataset']]['name']
            path = f"/AMDA/{mission_name}/{observatory_name}/{instrument_name}/{dataset_name}/{parameter['name']}"
            components = [component['name'] for component in parameter.get('components',[])]
            metadata = {key: item for key, item in parameter.items() if key is not 'components'}
            n_components = parameter.get('size', 0)
            if n_components == '3':
                metadata["type"] = "vector"
            elif parameter.get('display_type', '')=="spectrogram":
                metadata["type"] = "spectrogram"
            elif n_components != 0:
                metadata["type"] = "multicomponent"
            else:
                metadata["type"] = "scalar"
            products.append(Product(path, components, metadata))
        self.register_products(products)
        for _,mission in amda.mission.items():
            if ('target' in mission) and (mission['xml:id'] != 'Ephemerides') and (mission['target'] != 'Earth'):
                self.set_icon(f'/AMDA/{mission["name"]}','satellite')
        '''

    def get_data(self, metadata, start, stop):
        ts_type = amda_make_scalar
        try:
            param_id = metadata['xml:id']
            ts_type_str = metadata['type']
            if ts_type_str == 'vector':
                ts_type = amda_make_vector
            elif ts_type_str == 'multicomponent':
                ts_type = amda_make_multi_comp
            elif ts_type_str == 'spectrogram':
                ts_type = amda_make_spectro
            tstart = datetime.fromtimestamp(start, tz=timezone.utc)
            tend = datetime.fromtimestamp(stop, tz=timezone.utc)
            var = amda.get_parameter(start_time=tstart, stop_time=tend, parameter_id=param_id, method="REST")
            return ts_type(var)
        except Exception as e:
            print(traceback.format_exc())
            print("Error in amda.py ", str(e))
            return ts_type()

_amda = AmdaProvider()
