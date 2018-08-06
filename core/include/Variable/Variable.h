#ifndef SCIQLOP_VARIABLE_H
#define SCIQLOP_VARIABLE_H

#include "CoreGlobal.h"

#include <Data/DataSeriesIterator.h>
#include <Data/DataSeriesType.h>
#include <Data/SqpRange.h>

#include <QLoggingCategory>
#include <QObject>

#include <Common/MetaTypes.h>
#include <Common/spimpl.h>

Q_DECLARE_LOGGING_CATEGORY(LOG_Variable)

class IDataSeries;
class QString;

/**
 * @brief The Variable class represents a variable in SciQlop.
 */
class SCIQLOP_CORE_EXPORT Variable : public QObject {

    Q_OBJECT

public:
    explicit Variable(const QString &name, const QVariantHash &metadata = {});

    /// Copy ctor
    explicit Variable(const Variable &other);

    std::shared_ptr<Variable> clone() const;

    QString name() const noexcept;
    void setName(const QString &name) noexcept;
    DateTimeRange range() const noexcept;
    void setRange(const DateTimeRange &range) noexcept;
    DateTimeRange cacheRange() const noexcept;
    void setCacheRange(const DateTimeRange &cacheRange) noexcept;

    /// @return the number of points hold by the variable. The number of points is updated each time
    /// the data series changes
    int nbPoints() const noexcept;

    /// Returns the real range of the variable, i.e. the min and max x-axis values of the data
    /// series between the range of the variable. The real range is updated each time the variable
    /// range or the data series changed
    /// @return the real range, invalid range if the data series is null or empty
    /// @sa setDataSeries()
    /// @sa setRange()
    DateTimeRange realRange() const noexcept;

    /// @return the data of the variable, nullptr if there is no data
    std::shared_ptr<IDataSeries> dataSeries() const noexcept;

    /// @return the type of data that the variable holds
    DataSeriesType type() const noexcept;

    QVariantHash metadata() const noexcept;

    bool contains(const DateTimeRange &range) const noexcept;
    bool intersect(const DateTimeRange &range) const noexcept;
    bool isInside(const DateTimeRange &range) const noexcept;

    bool cacheContains(const DateTimeRange &range) const noexcept;
    bool cacheIntersect(const DateTimeRange &range) const noexcept;
    bool cacheIsInside(const DateTimeRange &range) const noexcept;

    QVector<DateTimeRange> provideNotInCacheRangeList(const DateTimeRange &range) const noexcept;
    QVector<DateTimeRange> provideInCacheRangeList(const DateTimeRange &range) const noexcept;
    void mergeDataSeries(std::shared_ptr<IDataSeries> dataSeries) noexcept;

    static QVector<DateTimeRange> provideNotInCacheRangeList(const DateTimeRange &oldRange,
                                                        const DateTimeRange &nextRange);

    static QVector<DateTimeRange> provideInCacheRangeList(const DateTimeRange &oldRange,
                                                     const DateTimeRange &nextRange);

signals:
    void updated();
    /// Signal emitted when when the data series of the variable is loaded for the first time
    void dataInitialized();

private:
    class VariablePrivate;
    spimpl::unique_impl_ptr<VariablePrivate> impl;
};

// Required for using shared_ptr in signals/slots
SCIQLOP_REGISTER_META_TYPE(VARIABLE_PTR_REGISTRY, std::shared_ptr<Variable>)
SCIQLOP_REGISTER_META_TYPE(VARIABLE_PTR_VECTOR_REGISTRY, QVector<std::shared_ptr<Variable> >)

#endif // SCIQLOP_VARIABLE_H
