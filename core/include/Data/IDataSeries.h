#ifndef SCIQLOP_IDATASERIES_H
#define SCIQLOP_IDATASERIES_H

#include <Common/MetaTypes.h>

#include <memory>

#include <QString>

template <int Dim>
class ArrayData;

struct Unit {
    explicit Unit(const QString &name = {}, bool timeUnit = false)
            : m_Name{name}, m_TimeUnit{timeUnit}
    {
    }

    inline bool operator==(const Unit &other) const
    {
        return std::tie(m_Name, m_TimeUnit) == std::tie(other.m_Name, other.m_TimeUnit);
    }
    inline bool operator!=(const Unit &other) const { return !(*this == other); }

    QString m_Name;  ///< Unit name
    bool m_TimeUnit; ///< The unit is a unit of time
};

/**
 * @brief The IDataSeries aims to declare a data series.
 *
 * A data series is an entity that contains at least :
 * - one dataset representing the x-axis
 * - one dataset representing the values
 *
 * Each dataset is represented by an ArrayData, and is associated with a unit.
 *
 * An ArrayData can be unidimensional or two-dimensional, depending on the implementation of the
 * IDataSeries. The x-axis dataset is always unidimensional.
 *
 * @sa ArrayData
 */
class IDataSeries {
public:
    virtual ~IDataSeries() noexcept = default;

    /// Returns the x-axis dataset
    virtual std::shared_ptr<ArrayData<1> > xAxisData() = 0;

    /// Returns the x-axis dataset (as const)
    virtual const std::shared_ptr<ArrayData<1> > xAxisData() const = 0;

    virtual Unit xAxisUnit() const = 0;

    virtual Unit valuesUnit() const = 0;

    virtual void merge(IDataSeries *dataSeries) = 0;

    virtual std::unique_ptr<IDataSeries> clone() const = 0;

    virtual void lockRead() = 0;
    virtual void lockWrite() = 0;
    virtual void unlock() = 0;
};

// Required for using shared_ptr in signals/slots
SCIQLOP_REGISTER_META_TYPE(IDATASERIES_PTR_REGISTRY, std::shared_ptr<IDataSeries>)

#endif // SCIQLOP_IDATASERIES_H
