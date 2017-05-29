#include "SqpApplication.h"

#include <DataSource/DataSourceController.h>
#include <QThread>

Q_LOGGING_CATEGORY(LOG_SqpApplication, "SqpApplication")

class SqpApplication::SqpApplicationPrivate {
public:
    SqpApplicationPrivate() {}
    virtual ~SqpApplicationPrivate()
    {
        qCInfo(LOG_SqpApplication()) << tr("Desctruction du SqpApplicationPrivate");
        m_DataSourceControllerThread.quit();
        m_DataSourceControllerThread.wait();
    }

    std::unique_ptr<DataSourceController> m_DataSourceController;
    QThread m_DataSourceControllerThread;
};


SqpApplication::SqpApplication(int &argc, char **argv)
        : QApplication(argc, argv), impl{spimpl::make_unique_impl<SqpApplicationPrivate>()}
{
    qCInfo(LOG_SqpApplication()) << tr("Construction du SqpApplication");

    impl->m_DataSourceController = std::make_unique<DataSourceController>();
    impl->m_DataSourceController->moveToThread(&impl->m_DataSourceControllerThread);

    connect(&impl->m_DataSourceControllerThread, &QThread::started,
            impl->m_DataSourceController.get(), &DataSourceController::initialize);
    connect(&impl->m_DataSourceControllerThread, &QThread::finished,
            impl->m_DataSourceController.get(), &DataSourceController::finalize);

    impl->m_DataSourceControllerThread.start();
}

SqpApplication::~SqpApplication()
{
}

void SqpApplication::initialize()
{
}
