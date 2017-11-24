#ifndef SCIQLOP_OPTIONALAXIS_H
#define SCIQLOP_OPTIONALAXIS_H

#include <Data/ArrayDataIterator.h>

#include "CoreGlobal.h"
#include "Unit.h"

#include <memory>

template <int Dim>
class ArrayData;

/**
 * @brief The OptionalAxis class defines an optional data axis for a series of data.
 *
 * An optional data axis is an axis that can be defined or not for a data series. If defined, it
 * contains a unit and data (1-dim ArrayData). It is then possible to access the data or the unit.
 * In the case of an undefined axis, the axis has no data and no unit. The methods for accessing the
 * data or the unit are always callable but will return undefined values.
 *
 * @sa DataSeries
 * @sa ArrayData
 */
class SCIQLOP_CORE_EXPORT OptionalAxis {
public:
    /// Ctor for an undefined axis
    explicit OptionalAxis();
    /// Ctor for a defined axis
    /// @param data the axis' data
    /// @param unit the axis' unit
    /// @throws std::invalid_argument if no data is associated to the axis
    explicit OptionalAxis(std::shared_ptr<ArrayData<1> > data, Unit unit);

    /// Copy ctor
    OptionalAxis(const OptionalAxis &other);
    /// Assignment operator
    OptionalAxis &operator=(OptionalAxis other);

    /// @return the flag that indicates if the axis is defined or not
    bool isDefined() const;

    ///@return the min and max values of the data on the axis, NaN values if there is no data
    std::pair<double, double> bounds() const;

    /// @return the number of data on the axis, 0 if the axis is not defined
    int size() const;
    /// @return the unit of the axis, an empty unit if the axis is not defined
    Unit unit() const;

    bool operator==(const OptionalAxis &other);
    bool operator!=(const OptionalAxis &other);

    // Iterators on data
    ArrayDataIterator begin();
    ArrayDataIterator end();
    ArrayDataIterator cbegin() const;
    ArrayDataIterator cend() const;

private:
    bool m_Defined;                        ///< Axis is defined or not
    std::shared_ptr<ArrayData<1> > m_Data; ///< Axis' data
    Unit m_Unit;                           ///< Axis' unit
};

#endif // SCIQLOP_OPTIONALAXIS_H
