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
 * template-parameter. In a case of a two-dimensional dataset, each dataset component has the same
 * number of values
 *
 * @tparam Dim the dimension of the ArrayData (one or two)
 * @sa IDataSeries
 */
template <int Dim>
class ArrayData {
public:
    /**
     * Ctor for a unidimensional ArrayData
     * @param data the data the ArrayData will hold
     */
    template <int D = Dim, typename = std::enable_if_t<D == 1> >
    explicit ArrayData(QVector<double> data) : m_Data{1, QVector<double>{}}
    {
        m_Data[0] = std::move(data);
    }

    /**
     * Ctor for a two-dimensional ArrayData. The number of components (number of vectors) must be
     * greater than 2 and each component must have the same number of values
     * @param data the data the ArrayData will hold
     * @throws std::invalid_argument if the number of components is less than 2
     * @remarks if the number of values is not the same for each component, no value is set
     */
    template <int D = Dim, typename = std::enable_if_t<D == 2> >
    explicit ArrayData(QVector<QVector<double> > data)
    {
        auto nbComponents = data.size();
        if (nbComponents < 2) {
            throw std::invalid_argument{
                QString{"A multidimensional ArrayData must have at least 2 components (found: %1"}
                    .arg(data.size())
                    .toStdString()};
        }

        auto nbValues = data.front().size();
        if (std::all_of(data.cbegin(), data.cend(), [nbValues](const auto &component) {
                return component.size() == nbValues;
            })) {
            m_Data = std::move(data);
        }
        else {
            m_Data = QVector<QVector<double> >{nbComponents, QVector<double>{}};
        }
    }

    /// Copy ctor
    explicit ArrayData(const ArrayData &other)
    {
        QReadLocker otherLocker{&other.m_Lock};
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

    /// @return the size (i.e. number of values) of a single component
    /// @remarks in a case of a two-dimensional ArrayData, each component has the same size
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

        auto nbComponents = m_Data.size();
        for (auto i = 0; i < nbComponents; ++i) {
            m_Data[i].clear();
        }
    }

private:
    QVector<QVector<double> > m_Data;
    mutable QReadWriteLock m_Lock;
};

#endif // SCIQLOP_ARRAYDATA_H
