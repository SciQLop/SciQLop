#ifndef SCIQLOP_ARRAYDATA_H
#define SCIQLOP_ARRAYDATA_H

#include <QReadLocker>
#include <QReadWriteLock>
#include <QVector>

#include <memory>

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
     * @return the data at a specified index
     * @remarks index must be a valid position
     * @remarks this method is only available for a unidimensional ArrayData
     */
    template <int D = Dim, typename = std::enable_if_t<D == 1> >
    double at(int index) const noexcept
    {
        QReadLocker locker{&m_Lock};
        return m_Data[0].at(index);
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

    /**
     * Merges into the array data an other array data
     * @param other the array data to merge with
     * @param prepend if true, the other array data is inserted at the beginning, otherwise it is
     * inserted at the end
     * @remarks this method is only available for a unidimensional ArrayData
     */
    template <int D = Dim, typename = std::enable_if_t<D == 1> >
    void add(const ArrayData<1> &other, bool prepend = false)
    {
        QWriteLocker locker{&m_Lock};
        if (!m_Data.empty()) {
            QReadLocker otherLocker{&other.m_Lock};

            if (prepend) {
                const auto &otherData = other.data();
                const auto otherDataSize = otherData.size();

                auto &data = m_Data[0];
                data.insert(data.begin(), otherDataSize, 0.);

                for (auto i = 0; i < otherDataSize; ++i) {
                    data.replace(i, otherData.at(i));
                }
            }
            else {
                m_Data[0] += other.data();
            }
        }
    }

    template <int D = Dim, typename = std::enable_if_t<D == 1> >
    int size() const
    {
        QReadLocker locker{&m_Lock};
        return m_Data[0].size();
    }

    template <int D = Dim, typename = std::enable_if_t<D == 1> >
    std::shared_ptr<ArrayData<Dim> > sort(const std::vector<int> sortPermutation)
    {
        QReadLocker locker{&m_Lock};

        const auto &data = m_Data.at(0);

        // Inits result
        auto sortedData = QVector<double>{};
        sortedData.resize(data.size());

        std::transform(sortPermutation.cbegin(), sortPermutation.cend(), sortedData.begin(),
                       [&data](int i) { return data[i]; });

        return std::make_shared<ArrayData<Dim> >(std::move(sortedData));
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
