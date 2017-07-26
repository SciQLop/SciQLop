#ifndef SCIQLOP_ARRAYDATA_H
#define SCIQLOP_ARRAYDATA_H

#include <QReadLocker>
#include <QReadWriteLock>
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
        QWriteLocker locker{&m_Lock};
        m_Data[0].resize(nbColumns);
    }

    /**
     * Ctor for a unidimensional ArrayData
     * @param data the data the ArrayData will hold
     */
    template <int D = Dim, typename = std::enable_if_t<D == 1> >
    explicit ArrayData(QVector<double> data) : m_Data{1, QVector<double>{}}
    {
        QWriteLocker locker{&m_Lock};
        m_Data[0] = std::move(data);
    }

    /// Copy ctor
    explicit ArrayData(const ArrayData &other)
    {
        QReadLocker otherLocker{&other.m_Lock};
        QWriteLocker locker{&m_Lock};
        m_Data = other.m_Data;
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
        QWriteLocker locker{&m_Lock};
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
        QReadLocker locker{&m_Lock};
        return m_Data[0];
    }

    /**
     * @return the data as a vector, as a const reference
     * @remarks this method is only available for a unidimensional ArrayData
     */
    template <int D = Dim, typename = std::enable_if_t<D == 1> >
    const QVector<double> &cdata() const noexcept
    {
        QReadLocker locker{&m_Lock};
        return m_Data.at(0);
    }

    // TODO Comment
    template <int D = Dim, typename = std::enable_if_t<D == 1> >
    void merge(const ArrayData<1> &arrayData)
    {
        QWriteLocker locker{&m_Lock};
        if (!m_Data.empty()) {
            QReadLocker otherLocker{&arrayData.m_Lock};
            m_Data[0] += arrayData.data();
        }
    }

    template <int D = Dim, typename = std::enable_if_t<D == 1> >
    int size() const
    {
        QReadLocker locker{&m_Lock};
        return m_Data[0].size();
    }

    void clear()
    {
        QWriteLocker locker{&m_Lock};
        m_Data.clear();
    }


private:
    QVector<QVector<double> > m_Data;
    mutable QReadWriteLock m_Lock;
};

#endif // SCIQLOP_ARRAYDATA_H
