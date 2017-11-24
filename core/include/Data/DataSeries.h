#ifndef SCIQLOP_DATASERIES_H
#define SCIQLOP_DATASERIES_H

#include "CoreGlobal.h"

#include <Common/SortUtils.h>

#include <Data/ArrayData.h>
#include <Data/DataSeriesMergeHelper.h>
#include <Data/IDataSeries.h>
#include <Data/OptionalAxis.h>

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
              m_ValuesIt(begin ? dataSeries.valuesData()->begin() : dataSeries.valuesData()->end()),
              m_YItBegin{dataSeries.yAxis().begin()},
              m_YItEnd{dataSeries.yAxis().end()}
    {
    }

    template <bool IC = IsConst, typename = std::enable_if_t<IC == true> >
    explicit IteratorValue(const DataSeries<Dim> &dataSeries, bool begin)
            : m_XIt(begin ? dataSeries.xAxisData()->cbegin() : dataSeries.xAxisData()->cend()),
              m_ValuesIt(begin ? dataSeries.valuesData()->cbegin()
                               : dataSeries.valuesData()->cend()),
              m_YItBegin{dataSeries.yAxis().cbegin()},
              m_YItEnd{dataSeries.yAxis().cend()}
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
        return std::tie(m_XIt, m_ValuesIt, m_YItBegin, m_YItEnd)
               == std::tie(otherImpl.m_XIt, otherImpl.m_ValuesIt, otherImpl.m_YItBegin,
                           otherImpl.m_YItEnd);
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
        result->next(offset);
        return result;
    }

    void next(int offset) override
    {
        m_XIt->next(offset);
        m_ValuesIt->next(offset);
    }

    void prev() override
    {
        --m_XIt;
        --m_ValuesIt;
    }

    double x() const override { return m_XIt->at(0); }
    std::vector<double> y() const override
    {
        std::vector<double> result{};
        std::transform(m_YItBegin, m_YItEnd, std::back_inserter(result),
                       [](const auto &it) { return it.first(); });

        return result;
    }

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
        m_YItBegin->impl()->swap(*otherImpl.m_YItBegin->impl());
        m_YItEnd->impl()->swap(*otherImpl.m_YItEnd->impl());
    }

private:
    ArrayDataIterator m_XIt;
    ArrayDataIterator m_ValuesIt;
    ArrayDataIterator m_YItBegin;
    ArrayDataIterator m_YItEnd;
};
} // namespace dataseries_detail

/**
 * @brief The DataSeries class is the base (abstract) implementation of IDataSeries.
 *
 * The DataSeries represents values on one or two axes, according to these rules:
 * - the x-axis is always defined
 * - an y-axis can be defined or not. If set, additional consistency checks apply to the values (see
 * below)
 * - the values are defined on one or two dimensions. In the case of 2-dim values, the data is
 * distributed into components (for example, a vector defines three components)
 * - New values can be added to the series, on the x-axis.
 * - Once initialized to the series creation, the y-axis (if defined) is no longer modifiable
 * - Data representing values and axes are associated with a unit
 * - The data series is always sorted in ascending order on the x-axis.
 *
 * Consistency checks are carried out between the axes and the values. These controls are provided
 * throughout the DataSeries lifecycle:
 * - the number of data on the x-axis must be equal to the number of values (in the case of
 * 2-dim ArrayData for values, the test is performed on the number of values per component)
 * - if the y-axis is defined, the number of components of the ArrayData for values must equal the
 * number of data on the y-axis.
 *
 * Examples:
 * 1)
 * - x-axis: [1 ; 2 ; 3]
 * - y-axis: not defined
 * - values: [10 ; 20 ; 30] (1-dim ArrayData)
 * => the DataSeries is valid, as x-axis and values have the same number of data
 *
 * 2)
 * - x-axis: [1 ; 2 ; 3]
 * - y-axis: not defined
 * - values: [10 ; 20 ; 30 ; 40] (1-dim ArrayData)
 * => the DataSeries is invalid, as x-axis and values haven't the same number of data
 *
 * 3)
 * - x-axis: [1 ; 2 ; 3]
 * - y-axis: not defined
 * - values: [10 ; 20 ; 30
 *            40 ; 50 ; 60] (2-dim ArrayData)
 * => the DataSeries is valid, as x-axis has 3 data and values contains 2 components with 3
 * data each
 *
 * 4)
 * - x-axis: [1 ; 2 ; 3]
 * - y-axis: [1 ; 2]
 * - values: [10 ; 20 ; 30
 *            40 ; 50 ; 60] (2-dim ArrayData)
 * => the DataSeries is valid, as:
 * - x-axis has 3 data and values contains 2 components with 3 data each AND
 * - y-axis has 2 data and values contains 2 components
 *
 * 5)
 * - x-axis: [1 ; 2 ; 3]
 * - y-axis: [1 ; 2 ; 3]
 * - values: [10 ; 20 ; 30
 *            40 ; 50 ; 60] (2-dim ArrayData)
 * => the DataSeries is invalid, as:
 * - x-axis has 3 data and values contains 2 components with 3 data each BUT
 * - y-axis has 3 data and values contains only 2 components
 *
 * @tparam Dim The dimension of the values data
 *
 */
template <int Dim>
class SCIQLOP_CORE_EXPORT DataSeries : public IDataSeries {
    friend class DataSeriesMergeHelper;

public:
    /// @sa IDataSeries::xAxisData()
    std::shared_ptr<ArrayData<1> > xAxisData() override { return m_XAxisData; }
    const std::shared_ptr<ArrayData<1> > xAxisData() const { return m_XAxisData; }

    /// @sa IDataSeries::xAxisUnit()
    Unit xAxisUnit() const override { return m_XAxisUnit; }

    /// @sa IDataSeries::yAxisUnit()
    Unit yAxisUnit() const override { return m_YAxis.unit(); }

    /// @return the values dataset
    std::shared_ptr<ArrayData<Dim> > valuesData() { return m_ValuesData; }
    const std::shared_ptr<ArrayData<Dim> > valuesData() const { return m_ValuesData; }

    /// @sa IDataSeries::valuesUnit()
    Unit valuesUnit() const override { return m_ValuesUnit; }

    int nbPoints() const override { return m_ValuesData->totalSize(); }

    std::pair<double, double> yBounds() const override { return m_YAxis.bounds(); }

    void clear()
    {
        m_XAxisData->clear();
        m_ValuesData->clear();
    }

    bool isEmpty() const noexcept { return m_XAxisData->size() == 0; }

    /// Merges into the data series an other data series.
    ///
    /// The two dataseries:
    /// - must be of the same dimension
    /// - must have the same y-axis (if defined)
    ///
    /// If the prerequisites are not valid, the method does nothing
    ///
    /// @remarks the data series to merge with is cleared after the operation
    void merge(IDataSeries *dataSeries) override
    {
        dataSeries->lockWrite();
        lockWrite();

        if (auto other = dynamic_cast<DataSeries<Dim> *>(dataSeries)) {
            if (m_YAxis == other->m_YAxis) {
                DataSeriesMergeHelper::merge(*other, *this);
            }
            else {
                qCWarning(LOG_DataSeries())
                    << QObject::tr("Can't merge data series that have not the same y-axis");
            }
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
        // Nothing to purge if series is empty
        if (isEmpty()) {
            return;
        }

        if (min > max) {
            std::swap(min, max);
        }

        // Nothing to purge if series min/max are inside purge range
        auto xMin = cbegin()->x();
        auto xMax = (--cend())->x();
        if (xMin >= min && xMax <= max) {
            return;
        }

        auto lowerIt = std::lower_bound(
            begin(), end(), min, [](const auto &it, const auto &val) { return it.x() < val; });
        erase(begin(), lowerIt);
        auto upperIt = std::upper_bound(
            begin(), end(), max, [](const auto &val, const auto &it) { return val < it.x(); });
        erase(upperIt, end());
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

    void insert(DataSeriesIterator first, DataSeriesIterator last, bool prepend = false)
    {
        auto firstImpl = dynamic_cast<dataseries_detail::IteratorValue<Dim, true> *>(first->impl());
        auto lastImpl = dynamic_cast<dataseries_detail::IteratorValue<Dim, true> *>(last->impl());

        if (firstImpl && lastImpl) {
            m_XAxisData->insert(firstImpl->m_XIt, lastImpl->m_XIt, prepend);
            m_ValuesData->insert(firstImpl->m_ValuesIt, lastImpl->m_ValuesIt, prepend);
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
            lowerIt, end, maxXAxisData,
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

    /// @return the y-axis associated to the data series
    const OptionalAxis &yAxis() const { return m_YAxis; }
    OptionalAxis &yAxis() { return m_YAxis; }

    // /////// //
    // Mutexes //
    // /////// //

    virtual void lockRead() { m_Lock.lockForRead(); }
    virtual void lockWrite() { m_Lock.lockForWrite(); }
    virtual void unlock() { m_Lock.unlock(); }

protected:
    /// Protected ctor (DataSeries is abstract).
    ///
    /// Data vectors must be consistent with each other, otherwise an exception will be thrown (@sa
    /// class description for consistent rules)
    /// @remarks data series is automatically sorted on its x-axis data
    /// @throws std::invalid_argument if the data are inconsistent with each other
    explicit DataSeries(std::shared_ptr<ArrayData<1> > xAxisData, const Unit &xAxisUnit,
                        std::shared_ptr<ArrayData<Dim> > valuesData, const Unit &valuesUnit,
                        OptionalAxis yAxis = OptionalAxis{})
            : m_XAxisData{xAxisData},
              m_XAxisUnit{xAxisUnit},
              m_ValuesData{valuesData},
              m_ValuesUnit{valuesUnit},
              m_YAxis{std::move(yAxis)}
    {
        if (m_XAxisData->size() != m_ValuesData->size()) {
            throw std::invalid_argument{
                "The number of values by component must be equal to the number of x-axis data"};
        }

        // Validates y-axis (if defined)
        if (yAxis.isDefined() && (yAxis.size() != m_ValuesData->componentCount())) {
            throw std::invalid_argument{
                "As the y-axis is defined, the number of value components must be equal to the "
                "number of y-axis data"};
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
              m_ValuesUnit{other.m_ValuesUnit},
              m_YAxis{other.m_YAxis}
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
        std::swap(m_YAxis, other.m_YAxis);

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

    // x-axis
    std::shared_ptr<ArrayData<1> > m_XAxisData;
    Unit m_XAxisUnit;

    // values
    std::shared_ptr<ArrayData<Dim> > m_ValuesData;
    Unit m_ValuesUnit;

    // y-axis (optional)
    OptionalAxis m_YAxis;

    QReadWriteLock m_Lock;
};

#endif // SCIQLOP_DATASERIES_H
