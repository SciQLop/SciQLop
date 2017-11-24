#ifndef SCIQLOP_DATASERIESITERATOR_H
#define SCIQLOP_DATASERIESITERATOR_H

#include "CoreGlobal.h"
#include "Data/SqpIterator.h"

#include <QVector>
#include <memory>

/**
 * @brief The DataSeriesIteratorValue class represents the current value of a data series iterator.
 * It offers standard access methods for the data in the series (x-axis, values), but it is up to
 * each series to define its own implementation of how to retrieve this data, by implementing the
 * DataSeriesIteratorValue::Impl interface
 *
 * @sa DataSeriesIterator
 */
class SCIQLOP_CORE_EXPORT DataSeriesIteratorValue {
public:
    struct Impl {
        virtual ~Impl() noexcept = default;
        virtual std::unique_ptr<Impl> clone() const = 0;
        virtual int distance(const Impl &other) const = 0;
        virtual bool equals(const Impl &other) const = 0;
        virtual bool lowerThan(const Impl &other) const = 0;
        virtual std::unique_ptr<Impl> advance(int offset) const = 0;
        virtual void next(int offset) = 0;
        virtual void prev() = 0;
        virtual double x() const = 0;
        virtual std::vector<double> y() const = 0;
        virtual double value() const = 0;
        virtual double value(int componentIndex) const = 0;
        virtual double minValue() const = 0;
        virtual double maxValue() const = 0;
        virtual QVector<double> values() const = 0;

        virtual void swap(Impl &other) = 0;
    };

    explicit DataSeriesIteratorValue(std::unique_ptr<Impl> impl);
    DataSeriesIteratorValue(const DataSeriesIteratorValue &other);
    DataSeriesIteratorValue &operator=(DataSeriesIteratorValue other);

    int distance(const DataSeriesIteratorValue &other) const;
    bool equals(const DataSeriesIteratorValue &other) const;
    bool lowerThan(const DataSeriesIteratorValue &other) const;

    DataSeriesIteratorValue advance(int offset) const;
    /// Advances to the next value
    void next(int offset = 1);
    /// Moves back to the previous value
    void prev();
    /// Gets x-axis data
    double x() const;
    /// Gets y-axis data
    std::vector<double> y() const;
    /// Gets value data
    double value() const;
    /// Gets value data depending on an index
    double value(int componentIndex) const;
    /// Gets min of all values data
    double minValue() const;
    /// Gets max of all values data
    double maxValue() const;
    /// Gets all values data
    QVector<double> values() const;

    Impl *impl();

    friend void swap(DataSeriesIteratorValue &lhs, DataSeriesIteratorValue &rhs)
    {
        std::swap(lhs.m_Impl, rhs.m_Impl);
    }

private:
    std::unique_ptr<Impl> m_Impl;
};

using DataSeriesIterator = SqpIterator<DataSeriesIteratorValue>;

#endif // SCIQLOP_DATASERIESITERATOR_H
