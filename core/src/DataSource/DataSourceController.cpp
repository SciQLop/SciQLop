#include "DataSource/DataSourceController.h"

#include <QMutex>
#include <QThread>

Q_LOGGING_CATEGORY(LOG_DataSourceController, "dataSourceController")

class DataSourceController::DataSourceControllerPrivate {
public:
    DataSourceControllerPrivate() {}

    QMutex m_WorkingMutex;
};

DataSourceController::DataSourceController(QObject *parent)
        : impl{spimpl::make_unique_impl<DataSourceControllerPrivate>()}
{
    qCDebug(LOG_DataSourceController()) << tr("Construction du DataSourceController")
                                        << QThread::currentThread();
}

DataSourceController::~DataSourceController()
{
    qCDebug(LOG_DataSourceController()) << tr("Desctruction du DataSourceController")
                                        << QThread::currentThread();
    this->waitForFinish();
}

void DataSourceController::initialize()
{
    qCDebug(LOG_DataSourceController()) << tr("initialize du DataSourceController")
                                        << QThread::currentThread();
    impl->m_WorkingMutex.lock();
    qCDebug(LOG_DataSourceController()) << tr("initialize du DataSourceController END");
}

void DataSourceController::finalize()
{
    impl->m_WorkingMutex.unlock();
}

void DataSourceController::waitForFinish()
{
    QMutexLocker locker(&impl->m_WorkingMutex);
}
