#include "Network/NetworkController.h"

#include <QMutex>
#include <QThread>

Q_LOGGING_CATEGORY(LOG_NetworkController, "NetworkController")

struct NetworkController::NetworkControllerPrivate {
    explicit NetworkControllerPrivate(NetworkController *parent) : m_WorkingMutex{} {}
    QMutex m_WorkingMutex;
};

NetworkController::NetworkController(QObject *parent)
        : QObject(parent), impl{spimpl::make_unique_impl<NetworkControllerPrivate>(this)}
{
}

void NetworkController::initialize()
{
    qCDebug(LOG_NetworkController()) << tr("NetworkController init") << QThread::currentThread();
    impl->m_WorkingMutex.lock();
    qCDebug(LOG_NetworkController()) << tr("NetworkController init END");
}

void NetworkController::finalize()
{
    impl->m_WorkingMutex.unlock();
}

void NetworkController::waitForFinish()
{
    QMutexLocker locker{&impl->m_WorkingMutex};
}
