#ifndef SCIQLOP_SIGNALWAITER_H
#define SCIQLOP_SIGNALWAITER_H

#include "CoreGlobal.h"

#include <QEventLoop>

/**
 * Class for synchronously waiting for the reception of a signal. The signal to wait is passed to
 * the construction of the object. When starting the wait, a timeout can be set to exit if the
 * signal has not been sent
 */
class SCIQLOP_CORE_EXPORT SignalWaiter : public QObject {
    Q_OBJECT
public:
    /**
     * Ctor
     * @param object the sender of the signal
     * @param signal the signal to listen
     */
    explicit SignalWaiter(QObject &sender, const char *signal);

    /**
     * Starts the signal and leaves after the signal has been received, or after the timeout
     * @param timeout the timeout set (if 0, uses a default timeout)
     * @return true if the signal was sent, false if the timeout occured
     */
    bool wait(int timeout);

private:
    bool m_Timeout;
    QEventLoop m_EventLoop;

private slots:
    void timeout();
};

#endif // SCIQLOP_SIGNALWAITER_H
