#ifndef SCIQLOP_NETWORKCONTROLLER_H
#define SCIQLOP_NETWORKCONTROLLER_H

#include <QLoggingCategory>
#include <QObject>

#include <Common/spimpl.h>

Q_DECLARE_LOGGING_CATEGORY(LOG_NetworkController)

/**
 * @brief The NetworkController class aims to handle all network connection of SciQlop.
 */
class NetworkController : public QObject {
    Q_OBJECT
public:
    explicit NetworkController(QObject *parent = 0);


    void initialize();
    void finalize();

private:
    void waitForFinish();

    class NetworkControllerPrivate;
    spimpl::unique_impl_ptr<NetworkControllerPrivate> impl;
};

#endif // SCIQLOP_NETWORKCONTROLLER_H
