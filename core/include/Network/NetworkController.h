#ifndef SCIQLOP_NETWORKCONTROLLER_H
#define SCIQLOP_NETWORKCONTROLLER_H

#include "CoreGlobal.h"

#include <QLoggingCategory>
#include <QObject>
#include <QUuid>

#include <Common/MetaTypes.h>
#include <Common/spimpl.h>
#include <functional>

Q_DECLARE_LOGGING_CATEGORY(LOG_NetworkController)

class QNetworkReply;
class QNetworkRequest;

/**
 * @brief The NetworkController class aims to handle all network connection of SciQlop.
 */
class SCIQLOP_CORE_EXPORT NetworkController : public QObject {
    Q_OBJECT
public:
    explicit NetworkController(QObject *parent = 0);

    void initialize();
    void finalize();

public slots:
    /// Execute request and call callback when the reply is finished. Identifier is attached to the
    /// callback
    void onProcessRequested(std::shared_ptr<QNetworkRequest> request, QUuid identifier,
                            std::function<void(QNetworkReply *, QUuid)> callback);
    /// Cancel the request of identifier
    void onReplyCanceled(QUuid identifier);

signals:
    void replyFinished(QNetworkReply *reply, QUuid identifier);
    void replyDownloadProgress(QUuid identifier, std::shared_ptr<QNetworkRequest> networkRequest,
                               double progress);

private:
    void waitForFinish();

    class NetworkControllerPrivate;
    spimpl::unique_impl_ptr<NetworkControllerPrivate> impl;
};

SCIQLOP_REGISTER_META_TYPE(NETWORKREQUEST_REGISTRY, std::shared_ptr<QNetworkRequest>)


#endif // SCIQLOP_NETWORKCONTROLLER_H
