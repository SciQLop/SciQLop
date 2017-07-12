#ifndef SCIQLOP_NETWORKCONTROLLER_H
#define SCIQLOP_NETWORKCONTROLLER_H

#include <QLoggingCategory>
#include <QObject>
#include <QUuid>

#include <Common/spimpl.h>
#include <functional>

Q_DECLARE_LOGGING_CATEGORY(LOG_NetworkController)

class QNetworkReply;
class QNetworkRequest;

/**
 * @brief The NetworkController class aims to handle all network connection of SciQlop.
 */
class NetworkController : public QObject {
    Q_OBJECT
public:
    explicit NetworkController(QObject *parent = 0);

    void initialize();
    void finalize();

public slots:
    /// Execute request and call callback when the reply is finished. Identifier is attached to the
    /// callback
    void onProcessRequested(const QNetworkRequest &request, QUuid identifier,
                            std::function<void(QNetworkReply *, QUuid)> callback);
    /// Cancel the request of identifier
    void onReplyCanceled(QUuid identifier);

signals:
    void replyFinished(QNetworkReply *reply, QUuid identifier);
    void replyDownloadProgress(QUuid identifier, double progress);

private:
    void waitForFinish();

    class NetworkControllerPrivate;
    spimpl::unique_impl_ptr<NetworkControllerPrivate> impl;
};

#endif // SCIQLOP_NETWORKCONTROLLER_H
