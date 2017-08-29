#ifndef SCIQLOP_ARRAYDATAITERATOR_H
#define SCIQLOP_ARRAYDATAITERATOR_H

#include "CoreGlobal.h"
#include "Data/SqpIterator.h"

#include <QVector>
#include <memory>

/**
 * @brief The ArrayDataIteratorValue class represents the current value of an array data iterator.
 * It offers standard access methods for the data in the series (at(), first()), but it is up to
 * each array data to define its own implementation of how to retrieve this data (one-dim or two-dim
 * array), by implementing the ArrayDataIteratorValue::Impl interface
 * @sa ArrayDataIterator
 */
class SCIQLOP_CORE_EXPORT ArrayDataIteratorValue {
public:
    struct Impl {
        virtual ~Impl() noexcept = default;
        virtual std::unique_ptr<Impl> clone() const = 0;
        virtual bool equals(const Impl &other) const = 0;
        virtual void next() = 0;
        virtual void prev() = 0;
        virtual double at(int componentIndex) const = 0;
        virtual double first() const = 0;
        virtual double min() const = 0;
        virtual double max() const = 0;
        virtual QVector<double> values() const = 0;
    };

    explicit ArrayDataIteratorValue(std::unique_ptr<Impl> impl);
    ArrayDataIteratorValue(const ArrayDataIteratorValue &other);
    ArrayDataIteratorValue(ArrayDataIteratorValue &&other) = default;
    ArrayDataIteratorValue &operator=(ArrayDataIteratorValue other);

    bool equals(const ArrayDataIteratorValue &other) const;

    /// Advances to the next value
    void next();
    /// Moves back to the previous value
    void prev();
    /// Gets value of a specified component
    double at(int componentIndex) const;
    /// Gets value of first component
    double first() const;
    /// Gets min value among all components
    double min() const;
    /// Gets max value among all components
    double max() const;
    /// Gets all values
    QVector<double> values() const;

private:
    std::unique_ptr<Impl> m_Impl;
};

using ArrayDataIterator = SqpIterator<ArrayDataIteratorValue>;

#endif // SCIQLOP_ARRAYDATAITERATOR_H
