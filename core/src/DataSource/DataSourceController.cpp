#include <DataSource/DataSourceController.h>

#include <QMutex>
#include <QThread>

#include <QDir>
#include <QStandardPaths>

Q_LOGGING_CATEGORY(LOG_DataSourceController, "DataSourceController")

class DataSourceController::DataSourceControllerPrivate {
public:
    QMutex m_WorkingMutex;
    QHash<QUuid, QString> m_DataSources;
};

DataSourceController::DataSourceController(QObject *parent)
        : impl{spimpl::make_unique_impl<DataSourceControllerPrivate>()}
{
    qCDebug(LOG_DataSourceController())
        << tr("DataSourceController construction") << QThread::currentThread();
}

DataSourceController::~DataSourceController()
{
    qCDebug(LOG_DataSourceController())
        << tr("DataSourceController destruction") << QThread::currentThread();
    this->waitForFinish();
}

QUuid DataSourceController::registerDataSource(const QString &dataSourceName) noexcept
{
    auto dataSourceUid = QUuid::createUuid();
    impl->m_DataSources.insert(dataSourceUid, dataSourceName);

    return dataSourceUid;
}

void DataSourceController::initialize()
{
    qCDebug(LOG_DataSourceController())
        << tr("DataSourceController init") << QThread::currentThread();
    impl->m_WorkingMutex.lock();
    qCDebug(LOG_DataSourceController()) << tr("DataSourceController init END");
}

void DataSourceController::finalize()
{
    impl->m_WorkingMutex.unlock();
}

void DataSourceController::waitForFinish()
{
    QMutexLocker locker{&impl->m_WorkingMutex};
}
