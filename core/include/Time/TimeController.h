#ifndef SCIQLOP_TIMECONTROLLER_H
#define SCIQLOP_TIMECONTROLLER_H

#include "CoreGlobal.h"

#include <Data/SqpRange.h>

#include <QLoggingCategory>
#include <QObject>

#include <Common/spimpl.h>


Q_DECLARE_LOGGING_CATEGORY(LOG_TimeController)

/**
 * @brief The TimeController class aims to handle the Time parameters notification in SciQlop.
 */
class SCIQLOP_CORE_EXPORT TimeController : public QObject {
    Q_OBJECT
public:
    explicit TimeController(QObject *parent = 0);

    DateTimeRange dateTime() const noexcept;

    /// Returns the MIME data associated to a time range
    static QByteArray mimeDataForTimeRange(const DateTimeRange &timeRange);

    /// Returns the time range contained in a MIME data
    static DateTimeRange timeRangeForMimeData(const QByteArray &mimeData);

signals:
    /// Signal emitted to notify that time parameters has beed updated
    void timeUpdated(DateTimeRange time);

public slots:
    /// Slot called when a new dateTime has been defined.
    void setDateTimeRange(DateTimeRange dateTime);

    /// Slot called when the dateTime has to be notified. Call timeUpdated signal
    void onTimeNotify();

private:
    class TimeControllerPrivate;
    spimpl::unique_impl_ptr<TimeControllerPrivate> impl;
};

#endif // SCIQLOP_TIMECONTROLLER_H
