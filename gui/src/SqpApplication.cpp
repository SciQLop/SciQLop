#include "SqpApplication.h"

#include <DataSource/DataSourceController.h>
#include <QThread>

Q_LOGGING_CATEGORY(LOG_SqpApplication, "SqpApplication")

class SqpApplication::SqpApplicationPrivate {
public:
    SqpApplicationPrivate() : m_DataSourceController{std::make_unique<DataSourceController>()}
    {
        m_DataSourceController->moveToThread(&m_DataSourceControllerThread);
    }

    virtual ~SqpApplicationPrivate()
    {
        qCInfo(LOG_SqpApplication()) << tr("SqpApplicationPrivate destruction");
        m_DataSourceControllerThread.quit();
        m_DataSourceControllerThread.wait();
    }

    std::unique_ptr<DataSourceController> m_DataSourceController;
    QThread m_DataSourceControllerThread;
};


SqpApplication::SqpApplication(int &argc, char **argv)
        : QApplication{argc, argv}, impl{spimpl::make_unique_impl<SqpApplicationPrivate>()}
{
    qCInfo(LOG_SqpApplication()) << tr("SqpApplication construction");

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

DataSourceController &SqpApplication::dataSourceController() const noexcept
{
    return *impl->m_DataSourceController;
}
