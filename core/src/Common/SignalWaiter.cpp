#include "Common/SignalWaiter.h"

#include <QTimer>

namespace {

const auto DEFAULT_TIMEOUT = 30000;

} // namespace

SignalWaiter::SignalWaiter(QObject &sender, const char *signal) : m_Timeout{false}
{
    connect(&sender, signal, &m_EventLoop, SLOT(quit()));
}

bool SignalWaiter::wait(int timeout)
{
    if (timeout == 0) {
        timeout = DEFAULT_TIMEOUT;
    }

    QTimer timer{};
    timer.setInterval(timeout);
    timer.start();
    connect(&timer, &QTimer::timeout, this, &SignalWaiter::timeout);

    m_EventLoop.exec();

    return !m_Timeout;
}

void SignalWaiter::timeout()
{
    m_Timeout = true;
    m_EventLoop.quit();
}
