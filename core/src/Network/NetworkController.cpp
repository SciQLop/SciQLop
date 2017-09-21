#include "Network/NetworkController.h"

#include <QMutex>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QReadWriteLock>
#include <QThread>

#include <unordered_map>

Q_LOGGING_CATEGORY(LOG_NetworkController, "NetworkController")

struct NetworkController::NetworkControllerPrivate {
    explicit NetworkControllerPrivate(NetworkController *parent) : m_WorkingMutex{} {}

    void lockRead() { m_Lock.lockForRead(); }
    void lockWrite() { m_Lock.lockForWrite(); }
    void unlock() { m_Lock.unlock(); }

    QMutex m_WorkingMutex;

    QReadWriteLock m_Lock;
    std::unordered_map<QNetworkReply *, QUuid> m_NetworkReplyToId;
    std::unique_ptr<QNetworkAccessManager> m_AccessManager{nullptr};
};

NetworkController::NetworkController(QObject *parent)
        : QObject(parent), impl{spimpl::make_unique_impl<NetworkControllerPrivate>(this)}
{
}

void NetworkController::onProcessRequested(std::shared_ptr<QNetworkRequest> request,
                                           QUuid identifier,
                                           std::function<void(QNetworkReply *, QUuid)> callback)
{
    qCDebug(LOG_NetworkController()) << tr("NetworkController onProcessRequested")
                                     << QThread::currentThread()->objectName() << &request;
    auto reply = impl->m_AccessManager->get(*request);

    // Store the couple reply id
    impl->lockWrite();
    impl->m_NetworkReplyToId[reply] = identifier;
    qCDebug(LOG_NetworkController()) << tr("Store for reply: ") << identifier;
    impl->unlock();

    auto onReplyFinished = [request, reply, this, identifier, callback]() {

        qCDebug(LOG_NetworkController()) << tr("NetworkController onReplyFinished")
                                         << QThread::currentThread() << request.get() << reply;
        impl->lockRead();
        auto it = impl->m_NetworkReplyToId.find(reply);
        if (it != impl->m_NetworkReplyToId.cend()) {
            qCDebug(LOG_NetworkController()) << tr("Remove for reply: ") << it->second;
            impl->unlock();
            impl->lockWrite();
            impl->m_NetworkReplyToId.erase(reply);
            impl->unlock();
            // Deletes reply
            callback(reply, identifier);
            reply->deleteLater();
        }
        else {
            impl->unlock();
        }

        qCDebug(LOG_NetworkController()) << tr("NetworkController onReplyFinished END")
                                         << QThread::currentThread() << reply;
    };

    auto onReplyProgress = [reply, request, this](qint64 bytesRead, qint64 totalBytes) {

        // NOTE: a totalbytes of 0 can happened when a request has been aborted
        if (totalBytes > 0) {
            double progress = (bytesRead * 100.0) / totalBytes;
            qCDebug(LOG_NetworkController()) << tr("NetworkController onReplyProgress") << progress
                                             << QThread::currentThread() << request.get() << reply
                                             << bytesRead << totalBytes;
            impl->lockRead();
            auto it = impl->m_NetworkReplyToId.find(reply);
            if (it != impl->m_NetworkReplyToId.cend()) {
                auto id = it->second;
                impl->unlock();
                emit this->replyDownloadProgress(id, request, progress);
            }
            else {
                impl->unlock();
            }

            qCDebug(LOG_NetworkController()) << tr("NetworkController onReplyProgress END")
                                             << QThread::currentThread() << reply;
        }
    };


    connect(reply, &QNetworkReply::finished, this, onReplyFinished);
    connect(reply, &QNetworkReply::downloadProgress, this, onReplyProgress);
    qCDebug(LOG_NetworkController()) << tr("NetworkController registered END")
                                     << QThread::currentThread()->objectName() << reply;
}

void NetworkController::initialize()
{
    qCDebug(LOG_NetworkController()) << tr("NetworkController init") << QThread::currentThread();
    impl->m_WorkingMutex.lock();
    impl->m_AccessManager = std::make_unique<QNetworkAccessManager>();


    auto onReplyErrors = [this](QNetworkReply *reply, const QList<QSslError> &errors) {
        qCCritical(LOG_NetworkController()) << tr("NetworkAcessManager errors: ") << errors;

    };


    connect(impl->m_AccessManager.get(), &QNetworkAccessManager::sslErrors, this, onReplyErrors);

    qCDebug(LOG_NetworkController()) << tr("NetworkController init END");
}

void NetworkController::finalize()
{
    impl->m_WorkingMutex.unlock();
}

void NetworkController::onReplyCanceled(QUuid identifier)
{
    auto findReply = [identifier](const auto &entry) { return identifier == entry.second; };
    qCDebug(LOG_NetworkController()) << tr("NetworkController onReplyCanceled")
                                     << QThread::currentThread() << identifier;


    impl->lockRead();
    auto end = impl->m_NetworkReplyToId.cend();
    auto it = std::find_if(impl->m_NetworkReplyToId.cbegin(), end, findReply);
    impl->unlock();
    if (it != end) {
        qCDebug(LOG_NetworkController()) << tr("NetworkController onReplyCanceled ABORT DONE")
                                         << QThread::currentThread() << identifier;
        it->first->abort();
    }
    qCDebug(LOG_NetworkController()) << tr("NetworkController onReplyCanceled END")
                                     << QThread::currentThread();
}

void NetworkController::waitForFinish()
{
    QMutexLocker locker{&impl->m_WorkingMutex};
}
