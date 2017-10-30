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

using DataContainer = std::vector<double>;

namespace arraydata_detail {

/// Struct used to sort ArrayData
template <int Dim>
struct Sort {
    static std::shared_ptr<ArrayData<Dim> > sort(const DataContainer &data, int nbComponents,
                                                 const std::vector<int> &sortPermutation)
    {
        return std::make_shared<ArrayData<Dim> >(
            SortUtils::sort(data, nbComponents, sortPermutation), nbComponents);
    }
};

/// Specialization for uni-dimensional ArrayData
template <>
struct Sort<1> {
    static std::shared_ptr<ArrayData<1> > sort(const DataContainer &data, int nbComponents,
                                               const std::vector<int> &sortPermutation)
    {
        Q_UNUSED(nbComponents)
        return std::make_shared<ArrayData<1> >(SortUtils::sort(data, 1, sortPermutation));
    }
};

template <int Dim, bool IsConst>
class IteratorValue;

template <int Dim, bool IsConst>
struct IteratorValueBuilder {
};

template <int Dim>
struct IteratorValueBuilder<Dim, true> {
    using DataContainerIterator = DataContainer::const_iterator;

    static void swap(IteratorValue<Dim, true> &o1, IteratorValue<Dim, true> &o2) {}
};

template <int Dim>
struct IteratorValueBuilder<Dim, false> {
    using DataContainerIterator = DataContainer::iterator;

    static void swap(IteratorValue<Dim, false> &o1, IteratorValue<Dim, false> &o2)
    {
        for (auto i = 0; i < o1.m_NbComponents; ++i) {
            std::iter_swap(o1.m_It + i, o2.m_It + i);
        }
    }
};

template <int Dim, bool IsConst>
class IteratorValue : public ArrayDataIteratorValue::Impl {
public:
    friend class ArrayData<Dim>;
    friend class IteratorValueBuilder<Dim, IsConst>;

    using DataContainerIterator =
        typename IteratorValueBuilder<Dim, IsConst>::DataContainerIterator;

    template <bool IC = IsConst, typename = std::enable_if_t<IC == true> >
    explicit IteratorValue(const DataContainer &container, int nbComponents, bool begin)
            : m_It{begin ? container.cbegin() : container.cend()}, m_NbComponents{nbComponents}
    {
    }

    template <bool IC = IsConst, typename = std::enable_if_t<IC == false> >
    explicit IteratorValue(DataContainer &container, int nbComponents, bool begin)
            : m_It{begin ? container.begin() : container.end()}, m_NbComponents{nbComponents}
    {
    }

    IteratorValue(const IteratorValue &other) = default;

    std::unique_ptr<ArrayDataIteratorValue::Impl> clone() const override
    {
        return std::make_unique<IteratorValue<Dim, IsConst> >(*this);
    }

    int distance(const ArrayDataIteratorValue::Impl &other) const override try {
        const auto &otherImpl = dynamic_cast<const IteratorValue &>(other);
        return std::distance(otherImpl.m_It, m_It) / m_NbComponents;
    }
    catch (const std::bad_cast &) {
        return 0;
    }

    bool equals(const ArrayDataIteratorValue::Impl &other) const override try {
        const auto &otherImpl = dynamic_cast<const IteratorValue &>(other);
        return std::tie(m_It, m_NbComponents) == std::tie(otherImpl.m_It, otherImpl.m_NbComponents);
    }
    catch (const std::bad_cast &) {
        return false;
    }

    bool lowerThan(const ArrayDataIteratorValue::Impl &other) const override try {
        const auto &otherImpl = dynamic_cast<const IteratorValue &>(other);
        return m_It < otherImpl.m_It;
    }
    catch (const std::bad_cast &) {
        return false;
    }

    std::unique_ptr<ArrayDataIteratorValue::Impl> advance(int offset) const override
    {
        auto result = clone();
        result->next(offset);
        return result;
    }

    void next(int offset) override { std::advance(m_It, offset * m_NbComponents); }
    void prev() override { std::advance(m_It, -m_NbComponents); }

    double at(int componentIndex) const override { return *(m_It + componentIndex); }
    double first() const override { return *m_It; }
    double min() const override
    {
        auto values = this->values();
        auto end = values.cend();
        auto it = std::min_element(values.cbegin(), end, [](const auto &v1, const auto &v2) {
            return SortUtils::minCompareWithNaN(v1, v2);
        });

        return it != end ? *it : std::numeric_limits<double>::quiet_NaN();
    }
    double max() const override
    {
        auto values = this->values();
        auto end = values.cend();
        auto it = std::max_element(values.cbegin(), end, [](const auto &v1, const auto &v2) {
            return SortUtils::maxCompareWithNaN(v1, v2);
        });
        return it != end ? *it : std::numeric_limits<double>::quiet_NaN();
    }

    QVector<double> values() const override
    {
        auto result = QVector<double>{};
        for (auto i = 0; i < m_NbComponents; ++i) {
            result.push_back(*(m_It + i));
        }

        return result;
    }

    void swap(ArrayDataIteratorValue::Impl &other) override
    {
        auto &otherImpl = dynamic_cast<IteratorValue &>(other);
        IteratorValueBuilder<Dim, IsConst>::swap(*this, otherImpl);
    }

private:
    DataContainerIterator m_It;
    int m_NbComponents;
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
    explicit ArrayData(DataContainer data) : m_Data{std::move(data)}, m_NbComponents{1}
    {
    }

    /**
     * Ctor for a two-dimensional ArrayData. The number of components (number of lines) must be
     * greater than 2 and must be a divisor of the total number of data in the vector
     * @param data the data the ArrayData will hold
     * @param nbComponents the number of components
     * @throws std::invalid_argument if the number of components is less than 2 or is not a divisor
     * of the size of the data
     */
    template <int D = Dim, typename = std::enable_if_t<D == 2> >
    explicit ArrayData(DataContainer data, int nbComponents)
            : m_Data{std::move(data)}, m_NbComponents{nbComponents}
    {
        if (nbComponents < 2) {
            throw std::invalid_argument{
                QString{"A multidimensional ArrayData must have at least 2 components (found: %1)"}
                    .arg(nbComponents)
                    .toStdString()};
        }

        if (m_Data.size() % m_NbComponents != 0) {
            throw std::invalid_argument{QString{
                "The number of components (%1) is inconsistent with the total number of data (%2)"}
                                            .arg(m_Data.size(), nbComponents)
                                            .toStdString()};
        }
    }

    /// Copy ctor
    explicit ArrayData(const ArrayData &other)
    {
        QReadLocker otherLocker{&other.m_Lock};
        m_Data = other.m_Data;
        m_NbComponents = other.m_NbComponents;
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

        if (m_NbComponents != other.componentCount()) {
            return;
        }

        insert(other.cbegin(), other.cend(), prepend);
    }

    void clear()
    {
        QWriteLocker locker{&m_Lock};
        m_Data.clear();
    }

    int componentCount() const noexcept { return m_NbComponents; }

    /// @return the size (i.e. number of values) of a single component
    /// @remarks in a case of a two-dimensional ArrayData, each component has the same size
    int size() const
    {
        QReadLocker locker{&m_Lock};
        return m_Data.size() / m_NbComponents;
    }

    /// @return the total size (i.e. number of values) of the array data
    int totalSize() const
    {
        QReadLocker locker{&m_Lock};
        return m_Data.size();
    }

    std::shared_ptr<ArrayData<Dim> > sort(const std::vector<int> &sortPermutation)
    {
        QReadLocker locker{&m_Lock};
        return arraydata_detail::Sort<Dim>::sort(m_Data, m_NbComponents, sortPermutation);
    }

    // ///////// //
    // Iterators //
    // ///////// //

    ArrayDataIterator begin()
    {
        return ArrayDataIterator{
            ArrayDataIteratorValue{std::make_unique<arraydata_detail::IteratorValue<Dim, false> >(
                m_Data, m_NbComponents, true)}};
    }

    ArrayDataIterator end()
    {
        return ArrayDataIterator{
            ArrayDataIteratorValue{std::make_unique<arraydata_detail::IteratorValue<Dim, false> >(
                m_Data, m_NbComponents, false)}};
    }

    ArrayDataIterator cbegin() const
    {
        return ArrayDataIterator{
            ArrayDataIteratorValue{std::make_unique<arraydata_detail::IteratorValue<Dim, true> >(
                m_Data, m_NbComponents, true)}};
    }

    ArrayDataIterator cend() const
    {
        return ArrayDataIterator{
            ArrayDataIteratorValue{std::make_unique<arraydata_detail::IteratorValue<Dim, true> >(
                m_Data, m_NbComponents, false)}};
    }

    void erase(ArrayDataIterator first, ArrayDataIterator last)
    {
        auto firstImpl = dynamic_cast<arraydata_detail::IteratorValue<Dim, false> *>(first->impl());
        auto lastImpl = dynamic_cast<arraydata_detail::IteratorValue<Dim, false> *>(last->impl());

        if (firstImpl && lastImpl) {
            m_Data.erase(firstImpl->m_It, lastImpl->m_It);
        }
    }

    void insert(ArrayDataIterator first, ArrayDataIterator last, bool prepend = false)
    {
        auto firstImpl = dynamic_cast<arraydata_detail::IteratorValue<Dim, true> *>(first->impl());
        auto lastImpl = dynamic_cast<arraydata_detail::IteratorValue<Dim, true> *>(last->impl());

        if (firstImpl && lastImpl) {
            auto insertIt = prepend ? m_Data.begin() : m_Data.end();

            m_Data.insert(insertIt, firstImpl->m_It, lastImpl->m_It);
        }
    }

    /**
     * @return the data at a specified index
     * @remarks index must be a valid position
     */
    double at(int index) const noexcept
    {
        QReadLocker locker{&m_Lock};
        return m_Data.at(index);
    }

    // ///////////// //
    // 1-dim methods //
    // ///////////// //

    /**
     * @return the data as a vector, as a const reference
     * @remarks this method is only available for a unidimensional ArrayData
     */
    template <int D = Dim, typename = std::enable_if_t<D == 1> >
    DataContainer cdata() const noexcept
    {
        return m_Data;
    }

private:
    DataContainer m_Data;
    /// Number of components (lines). Is always 1 in a 1-dim ArrayData
    int m_NbComponents;
    mutable QReadWriteLock m_Lock;
};

#endif // SCIQLOP_ARRAYDATA_H
