#ifndef SCIQLOP_DATASERIES_H
#define SCIQLOP_DATASERIES_H

#include "CoreGlobal.h"

#include <Common/SortUtils.h>

#include <Data/ArrayData.h>
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

template <int Dim>
class IteratorValue : public DataSeriesIteratorValue::Impl {
public:
    explicit IteratorValue(const DataSeries<Dim> &dataSeries, bool begin)
            : m_XIt(begin ? dataSeries.xAxisData()->cbegin() : dataSeries.xAxisData()->cend()),
              m_ValuesIt(begin ? dataSeries.valuesData()->cbegin()
                               : dataSeries.valuesData()->cend())
    {
    }
    IteratorValue(const IteratorValue &other) = default;

    std::unique_ptr<DataSeriesIteratorValue::Impl> clone() const override
    {
        return std::make_unique<IteratorValue<Dim> >(*this);
    }

    bool equals(const DataSeriesIteratorValue::Impl &other) const override try {
        const auto &otherImpl = dynamic_cast<const IteratorValue &>(other);
        return std::tie(m_XIt, m_ValuesIt) == std::tie(otherImpl.m_XIt, otherImpl.m_ValuesIt);
    }
    catch (const std::bad_cast &) {
        return false;
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

private:
    ArrayData<1>::Iterator m_XIt;
    typename ArrayData<Dim>::Iterator m_ValuesIt;
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
public:
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

    /// Merges into the data series an other data series
    /// @remarks the data series to merge with is cleared after the operation
    void merge(IDataSeries *dataSeries) override
    {
        dataSeries->lockWrite();
        lockWrite();

        if (auto other = dynamic_cast<DataSeries<Dim> *>(dataSeries)) {
            const auto &otherXAxisData = other->xAxisData()->cdata();
            const auto &xAxisData = m_XAxisData->cdata();

            // As data series are sorted, we can improve performances of merge, by call the sort
            // method only if the two data series overlap.
            if (!otherXAxisData.empty()) {
                auto firstValue = otherXAxisData.front();
                auto lastValue = otherXAxisData.back();

                auto xAxisDataBegin = xAxisData.cbegin();
                auto xAxisDataEnd = xAxisData.cend();

                bool prepend;
                bool sortNeeded;

                if (std::lower_bound(xAxisDataBegin, xAxisDataEnd, firstValue) == xAxisDataEnd) {
                    // Other data series if after data series
                    prepend = false;
                    sortNeeded = false;
                }
                else if (std::upper_bound(xAxisDataBegin, xAxisDataEnd, lastValue)
                         == xAxisDataBegin) {
                    // Other data series if before data series
                    prepend = true;
                    sortNeeded = false;
                }
                else {
                    // The two data series overlap
                    prepend = false;
                    sortNeeded = true;
                }

                // Makes the merge
                m_XAxisData->add(*other->xAxisData(), prepend);
                m_ValuesData->add(*other->valuesData(), prepend);

                if (sortNeeded) {
                    sort();
                }
            }

            // Clears the other data series
            other->clear();
        }
        else {
            qCWarning(LOG_DataSeries())
                << QObject::tr("Detection of a type of IDataSeries we cannot merge with !");
        }
        unlock();
        dataSeries->unlock();
    }

    // ///////// //
    // Iterators //
    // ///////// //

    DataSeriesIterator cbegin() const override
    {
        return DataSeriesIterator{DataSeriesIteratorValue{
            std::make_unique<dataseries_detail::IteratorValue<Dim> >(*this, true)}};
    }

    DataSeriesIterator cend() const override
    {
        return DataSeriesIterator{DataSeriesIteratorValue{
            std::make_unique<dataseries_detail::IteratorValue<Dim> >(*this, false)}};
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

        /// @todo ALX: complete

    }

    // /////// //
    // Mutexes //
    // /////// //

    virtual void lockRead() { m_Lock.lockForRead(); }
    virtual void lockWrite() { m_Lock.lockForWrite(); }
    virtual void unlock() { m_Lock.unlock(); }

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
