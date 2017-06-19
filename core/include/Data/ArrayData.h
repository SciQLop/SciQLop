#ifndef SCIQLOP_ARRAYDATA_H
#define SCIQLOP_ARRAYDATA_H

#include <QVector>

/**
 * @brief The ArrayData class represents a dataset for a data series.
 *
 * A dataset can be unidimensional or two-dimensional. This property is determined by the Dim
 * template-parameter.
 *
 * @tparam Dim the dimension of the ArrayData (one or two)
 * @sa IDataSeries
 */
template <int Dim>
class ArrayData {
public:
    /**
     * Ctor for a unidimensional ArrayData
     * @param nbColumns the number of values the ArrayData will hold
     */
    template <int D = Dim, typename = std::enable_if_t<D == 1> >
    explicit ArrayData(int nbColumns) : m_Data{1, QVector<double>{}}
    {
        m_Data[0].resize(nbColumns);
    }

    /**
     * Sets a data at a specified index. The index has to be valid to be effective
     * @param index the index to which the data will be set
     * @param data the data to set
     * @remarks this method is only available for a unidimensional ArrayData
     */
    template <int D = Dim, typename = std::enable_if_t<D == 1> >
    void setData(int index, double data) noexcept
    {
        if (index >= 0 && index < m_Data.at(0).size()) {
            m_Data[0].replace(index, data);
        }
    }

    /**
     * @return the data as a vector
     * @remarks this method is only available for a unidimensional ArrayData
     */
    template <int D = Dim, typename = std::enable_if_t<D == 1> >
    QVector<double> data() const noexcept
    {
        return m_Data.at(0);
    }

private:
    QVector<QVector<double> > m_Data;
};

#endif // SCIQLOP_ARRAYDATA_H
