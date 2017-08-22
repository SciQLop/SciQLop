#ifndef SCIQLOP_ARRAYDATA_H
#define SCIQLOP_ARRAYDATA_H

#include "Data/ArrayDataIterator.h"
#include <Common/SortUtils.h>

#include <QReadLocker>
#include <QReadWriteLock>
#include <QVector>

#include <memory>

template <int Dim>
class ArrayData;

using DataContainer = QVector<QVector<double> >;

namespace arraydata_detail {

/// Struct used to sort ArrayData
template <int Dim>
struct Sort {
    static std::shared_ptr<ArrayData<Dim> > sort(const DataContainer &data,
                                                 const std::vector<int> &sortPermutation)
    {
        auto nbComponents = data.size();
        auto sortedData = DataContainer(nbComponents);

        for (auto i = 0; i < nbComponents; ++i) {
            sortedData[i] = SortUtils::sort(data.at(i), sortPermutation);
        }

        return std::make_shared<ArrayData<Dim> >(std::move(sortedData));
    }
};

/// Specialization for uni-dimensional ArrayData
template <>
struct Sort<1> {
    static std::shared_ptr<ArrayData<1> > sort(const DataContainer &data,
                                               const std::vector<int> &sortPermutation)
    {
        return std::make_shared<ArrayData<1> >(SortUtils::sort(data.at(0), sortPermutation));
    }
};

template <int Dim>
class IteratorValue : public ArrayDataIteratorValue::Impl {
public:
    explicit IteratorValue(const DataContainer &container, bool begin) : m_Its{}
    {
        for (auto i = 0; i < container.size(); ++i) {
            m_Its.push_back(begin ? container.at(i).cbegin() : container.at(i).cend());
        }
    }

    IteratorValue(const IteratorValue &other) = default;

    std::unique_ptr<ArrayDataIteratorValue::Impl> clone() const override
    {
        return std::make_unique<IteratorValue<Dim> >(*this);
    }

    bool equals(const ArrayDataIteratorValue::Impl &other) const override try {
        const auto &otherImpl = dynamic_cast<const IteratorValue &>(other);
        return m_Its == otherImpl.m_Its;
    }
    catch (const std::bad_cast &) {
        return false;
    }

    void next() override
    {
        for (auto &it : m_Its) {
            ++it;
        }
    }

    void prev() override
    {
        for (auto &it : m_Its) {
            --it;
        }
    }

    double at(int componentIndex) const override { return *m_Its.at(componentIndex); }
    double first() const override { return *m_Its.front(); }
    double min() const override
    {
        auto end = m_Its.cend();
        auto it = std::min_element(m_Its.cbegin(), end, [](const auto &it1, const auto &it2) {
            return SortUtils::minCompareWithNaN(*it1, *it2);
        });
        return it != end ? **it : std::numeric_limits<double>::quiet_NaN();
    }
    double max() const override
    {
        auto end = m_Its.cend();
        auto it = std::max_element(m_Its.cbegin(), end, [](const auto &it1, const auto &it2) {
            return SortUtils::maxCompareWithNaN(*it1, *it2);
        });
        return it != end ? **it : std::numeric_limits<double>::quiet_NaN();
    }

private:
    std::vector<DataContainer::value_type::const_iterator> m_Its;
};

} // namespace arraydata_detail

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
    // ///// //
    // Ctors //
    // ///// //

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
    explicit ArrayData(DataContainer data)
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
            m_Data = DataContainer{nbComponents, QVector<double>{}};
        }
    }

    /// Copy ctor
    explicit ArrayData(const ArrayData &other)
    {
        QReadLocker otherLocker{&other.m_Lock};
        m_Data = other.m_Data;
    }

    // /////////////// //
    // General methods //
    // /////////////// //

    /**
     * Merges into the array data an other array data. The two array datas must have the same number
     * of components so the merge can be done
     * @param other the array data to merge with
     * @param prepend if true, the other array data is inserted at the beginning, otherwise it is
     * inserted at the end
     */
    void add(const ArrayData<Dim> &other, bool prepend = false)
    {
        QWriteLocker locker{&m_Lock};
        QReadLocker otherLocker{&other.m_Lock};

        auto nbComponents = m_Data.size();
        if (nbComponents != other.m_Data.size()) {
            return;
        }

        for (auto componentIndex = 0; componentIndex < nbComponents; ++componentIndex) {
            if (prepend) {
                const auto &otherData = other.data(componentIndex);
                const auto otherDataSize = otherData.size();

                auto &data = m_Data[componentIndex];
                data.insert(data.begin(), otherDataSize, 0.);

                for (auto i = 0; i < otherDataSize; ++i) {
                    data.replace(i, otherData.at(i));
                }
            }
            else {
                m_Data[componentIndex] += other.data(componentIndex);
            }
        }
    }

    void clear()
    {
        QWriteLocker locker{&m_Lock};

        auto nbComponents = m_Data.size();
        for (auto i = 0; i < nbComponents; ++i) {
            m_Data[i].clear();
        }
    }

    int componentCount() const noexcept { return m_Data.size(); }

    /**
     * @return the data of a component
     * @param componentIndex the index of the component to retrieve the data
     * @return the component's data, empty vector if the index is invalid
     */
    QVector<double> data(int componentIndex) const noexcept
    {
        QReadLocker locker{&m_Lock};

        return (componentIndex >= 0 && componentIndex < m_Data.size()) ? m_Data.at(componentIndex)
                                                                       : QVector<double>{};
    }

    /// @return the size (i.e. number of values) of a single component
    /// @remarks in a case of a two-dimensional ArrayData, each component has the same size
    int size() const
    {
        QReadLocker locker{&m_Lock};
        return m_Data[0].size();
    }

    std::shared_ptr<ArrayData<Dim> > sort(const std::vector<int> &sortPermutation)
    {
        QReadLocker locker{&m_Lock};
        return arraydata_detail::Sort<Dim>::sort(m_Data, sortPermutation);
    }

    // ///////// //
    // Iterators //
    // ///////// //

    ArrayDataIterator cbegin() const
    {
        return ArrayDataIterator{ArrayDataIteratorValue{
            std::make_unique<arraydata_detail::IteratorValue<Dim> >(m_Data, true)}};
    }
    ArrayDataIterator cend() const
    {
        return ArrayDataIterator{ArrayDataIteratorValue{
            std::make_unique<arraydata_detail::IteratorValue<Dim> >(m_Data, false)}};
    }

    // ///////////// //
    // 1-dim methods //
    // ///////////// //

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
     * @return the data as a vector
     * @remarks this method is only available for a unidimensional ArrayData
     */
    template <int D = Dim, typename = std::enable_if_t<D == 1> >
    QVector<double> data() const noexcept
    {
        QReadLocker locker{&m_Lock};
        return m_Data[0];
    }

    // ///////////// //
    // 2-dim methods //
    // ///////////// //

    /**
     * @return the data
     * @remarks this method is only available for a two-dimensional ArrayData
     */
    template <int D = Dim, typename = std::enable_if_t<D == 2> >
    DataContainer data() const noexcept
    {
        QReadLocker locker{&m_Lock};
        return m_Data;
    }

private:
    DataContainer m_Data;
    mutable QReadWriteLock m_Lock;
};

#endif // SCIQLOP_ARRAYDATA_H
