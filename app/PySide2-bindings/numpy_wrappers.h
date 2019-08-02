#ifndef NUMPY_WRAPPERS_H
#define NUMPY_WRAPPERS_H
#include <Data/ScalarTimeSerie.h>
#define NPY_NO_DEPRECATED_API NPY_1_7_API_VERSION
#if defined(slots) && (defined(__GNUC__) || defined(_MSC_VER) || defined(__clang__))
#pragma push_macro("slots")
#undef slots
extern "C"
{
/*
 * Python 2 uses the "register" keyword, which is deprecated in C++ 11
 * and forbidden in C++17.
 */
#if defined(__clang__)
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wdeprecated-register"
#endif

#include <Python.h>
#include <numpy/arrayobject.h>

#if defined(__clang__)
#pragma clang diagnostic pop
#endif
}
#else
#include <Python.h>
#include <numpy/arrayobject.h>
#endif
#include <assert.h>

inline int init_numpy()
{
    import_array(); // PyError if not successful
    return 0;
}
const static int numpy_initialized = init_numpy();
template <typename dest_type = PyObject>
struct PyObjectWrapper
{
private:
    PyObject* _py_obj;

    void inc_refcount()
    {
        if (_py_obj)
            Py_IncRef(_py_obj);
    }
    void dec_refcount()
    {
        if (_py_obj)
            Py_DecRef(_py_obj);
    }

public:
    PyObjectWrapper() : _py_obj { nullptr } {}
    PyObjectWrapper(const PyObjectWrapper& other) : _py_obj { other._py_obj } { inc_refcount(); };
    PyObjectWrapper(PyObjectWrapper&& other) : _py_obj { other._py_obj }
    {
        other._py_obj = nullptr;
    }
    PyObjectWrapper(PyObject* obj) : _py_obj { obj } { inc_refcount(); }
    ~PyObjectWrapper() { dec_refcount(); }
    PyObjectWrapper& operator=(PyObjectWrapper&& other)
    {
        this->_py_obj = other._py_obj;
        other._py_obj = nullptr;
        return *this;
    }
    PyObjectWrapper& operator=(const PyObjectWrapper& other)
    {
        dec_refcount();
        this->_py_obj = other._py_obj;
        inc_refcount();
        return *this;
    }

    PyObject* py_object() { return _py_obj; }
    inline dest_type* get() { return reinterpret_cast<dest_type*>(_py_obj); }
    inline bool is_null() { return _py_obj == nullptr; }
};

struct NpArray
{
private:
    PyObjectWrapper<PyArrayObject> _py_obj;
    NpArray(NpArray& other) = delete;
    NpArray(const NpArray& other) = delete;
    NpArray(const NpArray&& other) = delete;

public:
    static bool isNpArray(PyObject* obj)
    {
        return obj && PyArray_Check(reinterpret_cast<PyArrayObject*>(obj))
            && PyArray_IS_C_CONTIGUOUS(reinterpret_cast<PyArrayObject*>(obj));
    }
    NpArray() : _py_obj { nullptr } {}
    NpArray(NpArray&& other) : _py_obj { std::move(other._py_obj) } {}
    explicit NpArray(PyObject* obj) : _py_obj { obj }
    {
        std::cout << "NpArray ctor" << std::endl;
        assert(isNpArray(obj));
        assert(PyArray_ISFLOAT(_py_obj.get()));
    }

    NpArray& operator=(const NpArray& other)
    {
        this->_py_obj = other._py_obj;
        return *this;
    }

    NpArray& operator=(NpArray&& other)
    {
        this->_py_obj = std::move(other._py_obj);
        return *this;
    }

    std::vector<std::size_t> shape()
    {
        std::vector<std::size_t> shape;
        if (!_py_obj.is_null())
        {
            if (int ndim = PyArray_NDIM(_py_obj.get()); ndim > 0)
            {
                if (ndim < 10)
                {
                    shape.resize(ndim);
                    std::copy_n(PyArray_SHAPE(_py_obj.get()), ndim, std::begin(shape));
                }
            }
        }
        return shape;
    }

    std::size_t flat_size()
    {
        auto s = this->shape();
        return std::accumulate(std::cbegin(s), std::cend(s), 0);
    }

    double data(std::size_t pos)
    {
        if (!_py_obj.is_null())
        {
            return reinterpret_cast<double*>(PyArray_DATA(_py_obj.get()))[pos];
        }
        return nan("NAN");
    }

    std::vector<double> to_std_vect()
    {
        auto sz = flat_size();
        std::vector<double> v(sz);
        auto d_ptr = reinterpret_cast<double*>(PyArray_DATA(_py_obj.get()));
        std::copy(d_ptr, d_ptr + sz, std::begin(v));
        return v;
    }

    PyObject* py_object() { return _py_obj.py_object(); }
};

inline int test_np_array(NpArray& arr)
{
    auto shape = arr.shape();
    std::cout << "len(shape)=" << shape.size() << std::endl;
    std::for_each(std::cbegin(shape), std::cend(shape), [](auto sz) {
        static int i = 0;
        std::cout << "shape[" << i++ << "]=" << sz << std::endl;
    });
    auto flatsize = std::accumulate(std::cbegin(shape), std::cend(shape), 0);
    for (auto i = 0; i < flatsize; i++)
    {
        std::cout << "data[" << i << "]=" << arr.data(i) << std::endl;
    }
    return 1;
}

#endif //#ifndef NUMPY_WRAPPERS_H
