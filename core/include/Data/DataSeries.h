#ifndef SCIQLOP_DATASERIES_H
#define SCIQLOP_DATASERIES_H

#include "CoreGlobal.h"

#include <Common/SortUtils.h>

#include <Data/ArrayData.h>
#include <Data/DataSeriesMergeHelper.h>
#include <Data/IDataSeries.h>

#include <QLoggingCategory>
#include <QReadLocker>
#include <QReadWriteLock>
#include <memory>

// We don't use the Qt macro since the log is used in the header file, which causes multiple log
// definitions with inheritance. Inline method is used instead
inline const QLoggingCategory &LOG_DataSeries()
{
    static const QLoggingCategory category{"DataSeries"};
    return category;
}

template <int Dim>
class DataSeries;

namespace dataseries_detail {

template <int Dim, bool IsConst>
class IteratorValue : public DataSeriesIteratorValue::Impl {
public:
    friend class DataSeries<Dim>;

    template <bool IC = IsConst, typename = std::enable_if_t<IC == false> >
    explicit IteratorValue(DataSeries<Dim> &dataSeries, bool begin)
            : m_XIt(begin ? dataSeries.xAxisData()->begin() : dataSeries.xAxisData()->end()),
              m_ValuesIt(begin ? dataSeries.valuesData()->begin() : dataSeries.valuesData()->end())
    {
    }

    template <bool IC = IsConst, typename = std::enable_if_t<IC == true> >
    explicit IteratorValue(const DataSeries<Dim> &dataSeries, bool begin)
            : m_XIt(begin ? dataSeries.xAxisData()->cbegin() : dataSeries.xAxisData()->cend()),
              m_ValuesIt(begin ? dataSeries.valuesData()->cbegin()
                               : dataSeries.valuesData()->cend())
    {
    }

    IteratorValue(const IteratorValue &other) = default;

    std::unique_ptr<DataSeriesIteratorValue::Impl> clone() const override
    {
        return std::make_unique<IteratorValue<Dim, IsConst> >(*this);
    }

    int distance(const DataSeriesIteratorValue::Impl &other) const override try {
        const auto &otherImpl = dynamic_cast<const IteratorValue &>(other);
        return m_XIt->distance(*otherImpl.m_XIt);
    }
    catch (const std::bad_cast &) {
        return 0;
    }

    bool equals(const DataSeriesIteratorValue::Impl &other) const override try {
        const auto &otherImpl = dynamic_cast<const IteratorValue &>(other);
        return std::tie(m_XIt, m_ValuesIt) == std::tie(otherImpl.m_XIt, otherImpl.m_ValuesIt);
    }
    catch (const std::bad_cast &) {
        return false;
    }

    bool lowerThan(const DataSeriesIteratorValue::Impl &other) const override try {
        const auto &otherImpl = dynamic_cast<const IteratorValue &>(other);
        return m_XIt->lowerThan(*otherImpl.m_XIt);
    }
    catch (const std::bad_cast &) {
        return false;
    }

    std::unique_ptr<DataSeriesIteratorValue::Impl> advance(int offset) const override
    {
        auto result = clone();
        while (offset--) {
            result->next();
        }
        return result;
    }

    void next() override
    {
        ++m_XIt;
        ++m_ValuesIt;
    }

    void prev() override
    {
        --m_XIt;
        --m_ValuesIt;
    }

    double x() const override { return m_XIt->at(0); }
    double value() const override { return m_ValuesIt->at(0); }
    double value(int componentIndex) const override { return m_ValuesIt->at(componentIndex); }
    double minValue() const override { return m_ValuesIt->min(); }
    double maxValue() const override { return m_ValuesIt->max(); }
    QVector<double> values() const override { return m_ValuesIt->values(); }

    void swap(DataSeriesIteratorValue::Impl &other) override
    {
        auto &otherImpl = dynamic_cast<IteratorValue &>(other);
        m_XIt->impl()->swap(*otherImpl.m_XIt->impl());
        m_ValuesIt->impl()->swap(*otherImpl.m_ValuesIt->impl());
    }

private:
    ArrayDataIterator m_XIt;
    ArrayDataIterator m_ValuesIt;
};
} // namespace dataseries_detail

/**
 * @brief The DataSeries class is the base (abstract) implementation of IDataSeries.
 *
 * It proposes to set a dimension for the values ​​data.
 *
 * A DataSeries is always sorted on its x-axis data.
 *
 * @tparam Dim The dimension of the values data
 *
 */
template <int Dim>
class SCIQLOP_CORE_EXPORT DataSeries : public IDataSeries {
    friend class DataSeriesMergeHelper;

public:
    /// Tag needed to define the push_back() method
    /// @sa push_back()
    using value_type = DataSeriesIteratorValue;

    /// @sa IDataSeries::xAxisData()
    std::shared_ptr<ArrayData<1> > xAxisData() override { return m_XAxisData; }
    const std::shared_ptr<ArrayData<1> > xAxisData() const { return m_XAxisData; }

    /// @sa IDataSeries::xAxisUnit()
    Unit xAxisUnit() const override { return m_XAxisUnit; }

    /// @return the values dataset
    std::shared_ptr<ArrayData<Dim> > valuesData() { return m_ValuesData; }
    const std::shared_ptr<ArrayData<Dim> > valuesData() const { return m_ValuesData; }

    /// @sa IDataSeries::valuesUnit()
    Unit valuesUnit() const override { return m_ValuesUnit; }


    SqpRange range() const override
    {
        if (!m_XAxisData->cdata().isEmpty()) {
            return SqpRange{m_XAxisData->cdata().first(), m_XAxisData->cdata().last()};
        }

        return SqpRange{};
    }

    void clear()
    {
        m_XAxisData->clear();
        m_ValuesData->clear();
    }

    bool isEmpty() const noexcept { return m_XAxisData->size() == 0; }

    /// Merges into the data series an other data series
    /// @remarks the data series to merge with is cleared after the operation
    void merge(IDataSeries *dataSeries) override
    {
        dataSeries->lockWrite();
        lockWrite();

        if (auto other = dynamic_cast<DataSeries<Dim> *>(dataSeries)) {
            DataSeriesMergeHelper::merge(*other, *this);
        }
        else {
            qCWarning(LOG_DataSeries())
                << QObject::tr("Detection of a type of IDataSeries we cannot merge with !");
        }
        unlock();
        dataSeries->unlock();
    }

    void purge(double min, double max) override
    {
        if (min > max) {
            std::swap(min, max);
        }

        lockWrite();

        auto it = std::remove_if(
            begin(), end(), [min, max](const auto &it) { return it.x() < min || it.x() > max; });
        erase(it, end());

        unlock();
    }

    // ///////// //
    // Iterators //
    // ///////// //

    DataSeriesIterator begin() override
    {
        return DataSeriesIterator{DataSeriesIteratorValue{
            std::make_unique<dataseries_detail::IteratorValue<Dim, false> >(*this, true)}};
    }

    DataSeriesIterator end() override
    {
        return DataSeriesIterator{DataSeriesIteratorValue{
            std::make_unique<dataseries_detail::IteratorValue<Dim, false> >(*this, false)}};
    }

    DataSeriesIterator cbegin() const override
    {
        return DataSeriesIterator{DataSeriesIteratorValue{
            std::make_unique<dataseries_detail::IteratorValue<Dim, true> >(*this, true)}};
    }

    DataSeriesIterator cend() const override
    {
        return DataSeriesIterator{DataSeriesIteratorValue{
            std::make_unique<dataseries_detail::IteratorValue<Dim, true> >(*this, false)}};
    }

    void erase(DataSeriesIterator first, DataSeriesIterator last)
    {
        auto firstImpl
            = dynamic_cast<dataseries_detail::IteratorValue<Dim, false> *>(first->impl());
        auto lastImpl = dynamic_cast<dataseries_detail::IteratorValue<Dim, false> *>(last->impl());

        if (firstImpl && lastImpl) {
            m_XAxisData->erase(firstImpl->m_XIt, lastImpl->m_XIt);
            m_ValuesData->erase(firstImpl->m_ValuesIt, lastImpl->m_ValuesIt);
        }
    }

    /// @sa IDataSeries::minXAxisData()
    DataSeriesIterator minXAxisData(double minXAxisData) const override
    {
        return std::lower_bound(
            cbegin(), cend(), minXAxisData,
            [](const auto &itValue, const auto &value) { return itValue.x() < value; });
    }

    /// @sa IDataSeries::maxXAxisData()
    DataSeriesIterator maxXAxisData(double maxXAxisData) const override
    {
        // Gets the first element that greater than max value
        auto it = std::upper_bound(
            cbegin(), cend(), maxXAxisData,
            [](const auto &value, const auto &itValue) { return value < itValue.x(); });

        return it == cbegin() ? cend() : --it;
    }

    std::pair<DataSeriesIterator, DataSeriesIterator> xAxisRange(double minXAxisData,
                                                                 double maxXAxisData) const override
    {
        if (minXAxisData > maxXAxisData) {
            std::swap(minXAxisData, maxXAxisData);
        }

        auto begin = cbegin();
        auto end = cend();

        auto lowerIt = std::lower_bound(
            begin, end, minXAxisData,
            [](const auto &itValue, const auto &value) { return itValue.x() < value; });
        auto upperIt = std::upper_bound(
            begin, end, maxXAxisData,
            [](const auto &value, const auto &itValue) { return value < itValue.x(); });

        return std::make_pair(lowerIt, upperIt);
    }

    std::pair<DataSeriesIterator, DataSeriesIterator>
    valuesBounds(double minXAxisData, double maxXAxisData) const override
    {
        // Places iterators to the correct x-axis range
        auto xAxisRangeIts = xAxisRange(minXAxisData, maxXAxisData);

        // Returns end iterators if the range is empty
        if (xAxisRangeIts.first == xAxisRangeIts.second) {
            return std::make_pair(cend(), cend());
        }

        // Gets the iterator on the min of all values data
        auto minIt = std::min_element(
            xAxisRangeIts.first, xAxisRangeIts.second, [](const auto &it1, const auto &it2) {
                return SortUtils::minCompareWithNaN(it1.minValue(), it2.minValue());
            });

        // Gets the iterator on the max of all values data
        auto maxIt = std::max_element(
            xAxisRangeIts.first, xAxisRangeIts.second, [](const auto &it1, const auto &it2) {
                return SortUtils::maxCompareWithNaN(it1.maxValue(), it2.maxValue());
            });

        return std::make_pair(minIt, maxIt);
    }

    // /////// //
    // Mutexes //
    // /////// //

    virtual void lockRead() { m_Lock.lockForRead(); }
    virtual void lockWrite() { m_Lock.lockForWrite(); }
    virtual void unlock() { m_Lock.unlock(); }

    // ///// //
    // Other //
    // ///// //

    /// Inserts at the end of the data series the value of the iterator passed as a parameter. This
    /// method is intended to be used in the context of generating a back insert iterator
    /// @param iteratorValue the iterator value containing the values to insert
    /// @sa http://en.cppreference.com/w/cpp/iterator/back_inserter
    /// @sa merge()
    /// @sa value_type
    void push_back(const value_type &iteratorValue)
    {
        m_XAxisData->push_back(QVector<double>{iteratorValue.x()});
        m_ValuesData->push_back(iteratorValue.values());
    }

protected:
    /// Protected ctor (DataSeries is abstract). The vectors must have the same size, otherwise a
    /// DataSeries with no values will be created.
    /// @remarks data series is automatically sorted on its x-axis data
    explicit DataSeries(std::shared_ptr<ArrayData<1> > xAxisData, const Unit &xAxisUnit,
                        std::shared_ptr<ArrayData<Dim> > valuesData, const Unit &valuesUnit)
            : m_XAxisData{xAxisData},
              m_XAxisUnit{xAxisUnit},
              m_ValuesData{valuesData},
              m_ValuesUnit{valuesUnit}
    {
        if (m_XAxisData->size() != m_ValuesData->size()) {
            clear();
        }

        // Sorts data if it's not the case
        const auto &xAxisCData = m_XAxisData->cdata();
        if (!std::is_sorted(xAxisCData.cbegin(), xAxisCData.cend())) {
            sort();
        }
    }

    /// Copy ctor
    explicit DataSeries(const DataSeries<Dim> &other)
            : m_XAxisData{std::make_shared<ArrayData<1> >(*other.m_XAxisData)},
              m_XAxisUnit{other.m_XAxisUnit},
              m_ValuesData{std::make_shared<ArrayData<Dim> >(*other.m_ValuesData)},
              m_ValuesUnit{other.m_ValuesUnit}
    {
        // Since a series is ordered from its construction and is always ordered, it is not
        // necessary to call the sort method here ('other' is sorted)
    }

    /// Assignment operator
    template <int D>
    DataSeries &operator=(DataSeries<D> other)
    {
        std::swap(m_XAxisData, other.m_XAxisData);
        std::swap(m_XAxisUnit, other.m_XAxisUnit);
        std::swap(m_ValuesData, other.m_ValuesData);
        std::swap(m_ValuesUnit, other.m_ValuesUnit);

        return *this;
    }

private:
    /**
     * Sorts data series on its x-axis data
     */
    void sort() noexcept
    {
        auto permutation = SortUtils::sortPermutation(*m_XAxisData, std::less<double>());
        m_XAxisData = m_XAxisData->sort(permutation);
        m_ValuesData = m_ValuesData->sort(permutation);
    }

    std::shared_ptr<ArrayData<1> > m_XAxisData;
    Unit m_XAxisUnit;
    std::shared_ptr<ArrayData<Dim> > m_ValuesData;
    Unit m_ValuesUnit;

    QReadWriteLock m_Lock;
};

#endif // SCIQLOP_DATASERIES_H
