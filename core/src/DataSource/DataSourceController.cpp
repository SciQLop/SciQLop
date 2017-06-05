#include <DataSource/DataSourceController.h>
#include <DataSource/DataSourceItem.h>

#include <QMutex>
#include <QThread>

#include <QDir>
#include <QStandardPaths>

Q_LOGGING_CATEGORY(LOG_DataSourceController, "DataSourceController")

class DataSourceController::DataSourceControllerPrivate {
public:
    QMutex m_WorkingMutex;
    /// Data sources registered
    QHash<QUuid, QString> m_DataSources;
    /// Data sources structures
    std::map<QUuid, std::unique_ptr<DataSourceItem> > m_DataSourceItems;
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

void DataSourceController::setDataSourceItem(
    const QUuid &dataSourceUid, std::unique_ptr<DataSourceItem> dataSourceItem) noexcept
{
    if (impl->m_DataSources.contains(dataSourceUid)) {
        impl->m_DataSourceItems.insert(std::make_pair(dataSourceUid, std::move(dataSourceItem)));

        // Retrieves the data source item to emit the signal with it
        auto it = impl->m_DataSourceItems.find(dataSourceUid);
        if (it != impl->m_DataSourceItems.end()) {
            emit dataSourceItemSet(*it->second);
        }
    }
    else {
        qCWarning(LOG_DataSourceController()) << tr("Can't set data source item for uid %1 : no "
                                                    "data source has been registered with the uid")
                                                     .arg(dataSourceUid.toString());
    }
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
