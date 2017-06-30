#ifndef SCIQLOP_TIMECONTROLLER_H
#define SCIQLOP_TIMECONTROLLER_H

#include <Data/SqpDateTime.h>

#include <QLoggingCategory>
#include <QObject>

#include <Common/spimpl.h>


Q_DECLARE_LOGGING_CATEGORY(LOG_TimeController)

/**
 * @brief The TimeController class aims to handle the Time parameters notification in SciQlop.
 */
class TimeController : public QObject {
    Q_OBJECT
public:
    explicit TimeController(QObject *parent = 0);

    SqpDateTime dateTime() const noexcept;

signals:
    /// Signal emitted to notify that time parameters has beed updated
    void timeUpdated(SqpDateTime time);

public slots:
    /// Slot called when a new dateTime has been defined.
    void onTimeToUpdate(SqpDateTime dateTime);

    /// Slot called when the dateTime has to be notified. Call timeUpdated signal
    void onTimeNotify();

private:
    class TimeControllerPrivate;
    spimpl::unique_impl_ptr<TimeControllerPrivate> impl;
};

#endif // SCIQLOP_TIMECONTROLLER_H
