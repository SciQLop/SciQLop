#ifndef SCIQLOP_DATASERIESITERATOR_H
#define SCIQLOP_DATASERIESITERATOR_H

#include "CoreGlobal.h"

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
        virtual bool equals(const Impl &other) const = 0;
        virtual void next() = 0;
        virtual void prev() = 0;
        virtual double x() const = 0;
        virtual double value() const = 0;
        virtual double value(int componentIndex) const = 0;
    };

    explicit DataSeriesIteratorValue(std::unique_ptr<Impl> impl);
    DataSeriesIteratorValue(const DataSeriesIteratorValue &other);
    DataSeriesIteratorValue(DataSeriesIteratorValue &&other) = default;
    DataSeriesIteratorValue &operator=(DataSeriesIteratorValue other);

    bool equals(const DataSeriesIteratorValue &other) const;

    /// Advances to the next value
    void next();
    /// Moves back to the previous value
    void prev();
    /// Gets x-axis data
    double x() const;
    /// Gets value data
    double value() const;
    /// Gets value data depending on an index
    double value(int componentIndex) const;

private:
    std::unique_ptr<Impl> m_Impl;
};

/**
 * @brief The DataSeriesIterator class represents an iterator used for data series. It defines all
 * operators needed for a standard forward iterator
 * @sa http://www.cplusplus.com/reference/iterator/
 */
class SCIQLOP_CORE_EXPORT DataSeriesIterator {
public:
    using iterator_category = std::forward_iterator_tag;
    using value_type = const DataSeriesIteratorValue;
    using difference_type = std::ptrdiff_t;
    using pointer = value_type *;
    using reference = value_type &;

    explicit DataSeriesIterator(DataSeriesIteratorValue value);
    virtual ~DataSeriesIterator() noexcept = default;
    DataSeriesIterator(const DataSeriesIterator &) = default;
    DataSeriesIterator(DataSeriesIterator &&) = default;
    DataSeriesIterator &operator=(const DataSeriesIterator &) = default;
    DataSeriesIterator &operator=(DataSeriesIterator &&) = default;

    DataSeriesIterator &operator++();
    DataSeriesIterator &operator--();
    pointer operator->() const { return &m_CurrentValue; }
    reference operator*() const { return m_CurrentValue; }
    bool operator==(const DataSeriesIterator &other) const;
    bool operator!=(const DataSeriesIterator &other) const;

private:
    DataSeriesIteratorValue m_CurrentValue;
};

#endif // SCIQLOP_DATASERIESITERATOR_H
