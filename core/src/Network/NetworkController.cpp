#include "Network/NetworkController.h"

#include <QMutex>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QThread>

Q_LOGGING_CATEGORY(LOG_NetworkController, "NetworkController")

struct NetworkController::NetworkControllerPrivate {
    explicit NetworkControllerPrivate(NetworkController *parent)
            : m_WorkingMutex{}, m_AccessManager{std::make_unique<QNetworkAccessManager>()}
    {
    }
    QMutex m_WorkingMutex;

    std::unique_ptr<QNetworkAccessManager> m_AccessManager{nullptr};
};

NetworkController::NetworkController(QObject *parent)
        : QObject(parent), impl{spimpl::make_unique_impl<NetworkControllerPrivate>(this)}
{

}

void NetworkController::execute(QNetworkReply *reply)
{
    auto replyReadyToRead =[reply, this] () {
           auto content = reply->readAll();

           emit this->replyToRead();
       };

    connect(impl->m_Reply, &QNetworkReply::finished, this, replyReadyToRead);
    connect(impl->m_Reply, &QNetworkReply::aboutToClose, this, replyReadyToRead);
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
