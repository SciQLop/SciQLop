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
    qCInfo(LOG_DataSourceController()) << tr("Construction du DataSourceController");
}

DataSourceController::~DataSourceController()
{
    //    delete impl;
    this->waitForFinish();
}

void DataSourceController::initialize()
{
    qCInfo(LOG_DataSourceController()) << tr("initialize du DataSourceController");
    impl->m_WorkingMutex.lock();
    qCInfo(LOG_DataSourceController()) << tr("initialize du DataSourceController END");
}

void DataSourceController::finalize()
{
    qCInfo(LOG_DataSourceController()) << tr("finalize du DataSourceController");
    impl->m_WorkingMutex.unlock();
    qCInfo(LOG_DataSourceController()) << tr("finalize du DataSourceController END");
}

void DataSourceController::waitForFinish()
{
    qCInfo(LOG_DataSourceController()) << tr("waitForFinish du DataSourceController");
    QMutexLocker locker(&impl->m_WorkingMutex);
    qCInfo(LOG_DataSourceController()) << tr("waitForFinish du DataSourceController END");
}
