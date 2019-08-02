#include "numpy_wrappers.h"

// ScalarTimeSerie ScalarTimeSerie_from_np(PyObject* time, PyObject* values)
//{
//    assert(time);
//    assert(values);
//    assert(PyArray_NDIM(time) == 1);
//    assert(PyArray_NDIM(values) == 1);
//    assert(PyArray_ISFLOAT(time));
//    assert(PyArray_ISFLOAT(values));
//    assert(PyArray_DIM(time, 0) == PyArray_DIM(values, 0));
//    assert(PyArray_IS_C_CONTIGUOUS(time));
//    assert(PyArray_IS_C_CONTIGUOUS(values));
//    int size = PyArray_DIM(time, 0);
//    ScalarTimeSerie ts(size);
//    for (int i = 0; i < size; i++)
//    {
//    }
//}
