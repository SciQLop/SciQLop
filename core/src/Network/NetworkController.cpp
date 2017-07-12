#include "Network/NetworkController.h"

#include <QMutex>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QThread>

#include <unordered_map>

Q_LOGGING_CATEGORY(LOG_NetworkController, "NetworkController")

struct NetworkController::NetworkControllerPrivate {
    explicit NetworkControllerPrivate(NetworkController *parent) : m_WorkingMutex{} {}
    QMutex m_WorkingMutex;

    std::unordered_map<QNetworkReply *, QUuid> m_NetworkReplyToVariableId;
    std::unique_ptr<QNetworkAccessManager> m_AccessManager{nullptr};
};

NetworkController::NetworkController(QObject *parent)
        : QObject(parent), impl{spimpl::make_unique_impl<NetworkControllerPrivate>(this)}
{
}

void NetworkController::onProcessRequested(const QNetworkRequest &request, QUuid identifier,
                                           std::function<void(QNetworkReply *, QUuid)> callback)
{
    qCInfo(LOG_NetworkController()) << tr("NetworkController registered")
                                    << QThread::currentThread();
    auto reply = impl->m_AccessManager->get(request);

    // Store the couple reply id
    impl->m_NetworkReplyToVariableId[reply] = identifier;

    auto onReplyFinished = [reply, this, identifier, callback]() {

        qCInfo(LOG_NetworkController()) << tr("NetworkController onReplyFinished")
                                        << QThread::currentThread();
        auto it = impl->m_NetworkReplyToVariableId.find(reply);
        if (it != impl->m_NetworkReplyToVariableId.cend()) {
            callback(reply, identifier);
        }
    };

    auto onReplyProgress = [reply, this](qint64 bytesRead, qint64 totalBytes) {

        double progress = (bytesRead * 100.0) / totalBytes;
        auto it = impl->m_NetworkReplyToVariableId.find(reply);
        if (it != impl->m_NetworkReplyToVariableId.cend()) {
            emit this->replyDownloadProgress(it->second, progress);
        }
    };


    connect(reply, &QNetworkReply::finished, this, onReplyFinished);
    connect(reply, &QNetworkReply::downloadProgress, this, onReplyProgress);
}

void NetworkController::initialize()
{
    qCDebug(LOG_NetworkController()) << tr("NetworkController init") << QThread::currentThread();
    impl->m_WorkingMutex.lock();
    impl->m_AccessManager = std::make_unique<QNetworkAccessManager>();
    qCDebug(LOG_NetworkController()) << tr("NetworkController init END");
}

void NetworkController::finalize()
{
    impl->m_WorkingMutex.unlock();
}

void NetworkController::onReplyCanceled(QUuid identifier)
{
    auto findReply = [identifier](const auto &entry) { return identifier == entry.second; };

    auto end = impl->m_NetworkReplyToVariableId.cend();
    auto it = std::find_if(impl->m_NetworkReplyToVariableId.cbegin(), end, findReply);
    if (it != end) {
        it->first->abort();
    }
}

void NetworkController::waitForFinish()
{
    QMutexLocker locker{&impl->m_WorkingMutex};
}
