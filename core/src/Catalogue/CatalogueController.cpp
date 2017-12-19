#include <Catalogue/CatalogueController.h>

#include <Variable/Variable.h>

#include <CatalogueDao.h>

#include <ComparaisonPredicate.h>
#include <CompoundPredicate.h>
#include <DBCatalogue.h>
#include <DBEvent.h>
#include <DBEventProduct.h>
#include <DBTag.h>
#include <IRequestPredicate.h>

#include <QDataStream>
#include <QMutex>
#include <QThread>

#include <QDir>
#include <QStandardPaths>

Q_LOGGING_CATEGORY(LOG_CatalogueController, "CatalogueController")

namespace {

static QString REPOSITORY_WORK_SUFFIX = QString{"_work"};
static QString REPOSITORY_TRASH_SUFFIX = QString{"_trash"};
}

class CatalogueController::CatalogueControllerPrivate {

public:
    explicit CatalogueControllerPrivate(CatalogueController *parent) : m_Q{parent} {}

    QMutex m_WorkingMutex;
    CatalogueDao m_CatalogueDao;

    QStringList m_RepositoryList;
    CatalogueController *m_Q;

    void copyDBtoDB(const QString &dbFrom, const QString &dbTo);
    QString toWorkRepository(QString repository);
    QString toSyncRepository(QString repository);
    void savAllDB();

    void saveEvent(std::shared_ptr<DBEvent> event, bool persist = true);
    void saveCatalogue(std::shared_ptr<DBCatalogue> catalogue, bool persist = true);
};

CatalogueController::CatalogueController(QObject *parent)
        : impl{spimpl::make_unique_impl<CatalogueControllerPrivate>(this)}
{
    qCDebug(LOG_CatalogueController()) << tr("CatalogueController construction")
                                       << QThread::currentThread();
}

CatalogueController::~CatalogueController()
{
    qCDebug(LOG_CatalogueController()) << tr("CatalogueController destruction")
                                       << QThread::currentThread();
    this->waitForFinish();
}

QStringList CatalogueController::getRepositories() const
{
    return impl->m_RepositoryList;
}

void CatalogueController::addDB(const QString &dbPath)
{
    QDir dbDir(dbPath);
    if (dbDir.exists()) {
        auto dirName = dbDir.dirName();

        if (std::find(impl->m_RepositoryList.cbegin(), impl->m_RepositoryList.cend(), dirName)
            != impl->m_RepositoryList.cend()) {
            qCCritical(LOG_CatalogueController())
                << tr("Impossible to addDB that is already loaded");
        }

        if (!impl->m_CatalogueDao.addDB(dbPath, dirName)) {
            qCCritical(LOG_CatalogueController())
                << tr("Impossible to addDB %1 from %2 ").arg(dirName, dbPath);
        }
        else {
            impl->m_RepositoryList << dirName;
            impl->copyDBtoDB(dirName, impl->toWorkRepository(dirName));
        }
    }
    else {
        qCCritical(LOG_CatalogueController()) << tr("Impossible to addDB that not exists: ")
                                              << dbPath;
    }
}

void CatalogueController::saveDB(const QString &destinationPath, const QString &repository)
{
    if (!impl->m_CatalogueDao.saveDB(destinationPath, repository)) {
        qCCritical(LOG_CatalogueController())
            << tr("Impossible to saveDB %1 from %2 ").arg(repository, destinationPath);
    }
}

std::list<std::shared_ptr<DBEvent> >
CatalogueController::retrieveEvents(const QString &repository) const
{
    QString dbDireName = repository.isEmpty() ? REPOSITORY_DEFAULT : repository;

    auto eventsShared = std::list<std::shared_ptr<DBEvent> >{};
    auto events = impl->m_CatalogueDao.getEvents(impl->toWorkRepository(dbDireName));
    for (auto event : events) {
        eventsShared.push_back(std::make_shared<DBEvent>(event));
    }
    return eventsShared;
}

std::list<std::shared_ptr<DBEvent> > CatalogueController::retrieveAllEvents() const
{
    auto eventsShared = std::list<std::shared_ptr<DBEvent> >{};
    for (auto repository : impl->m_RepositoryList) {
        eventsShared.splice(eventsShared.end(), retrieveEvents(repository));
    }

    return eventsShared;
}

std::list<std::shared_ptr<DBEvent> >
CatalogueController::retrieveEventsFromCatalogue(std::shared_ptr<DBCatalogue> catalogue) const
{
    auto eventsShared = std::list<std::shared_ptr<DBEvent> >{};
    auto events = impl->m_CatalogueDao.getCatalogueEvents(*catalogue);
    for (auto event : events) {
        eventsShared.push_back(std::make_shared<DBEvent>(event));
    }
    return eventsShared;
}

void CatalogueController::updateEvent(std::shared_ptr<DBEvent> event)
{
    event->setRepository(impl->toWorkRepository(event->getRepository()));

    impl->m_CatalogueDao.updateEvent(*event);
}

void CatalogueController::updateEventProduct(std::shared_ptr<DBEventProduct> eventProduct)
{
    impl->m_CatalogueDao.updateEventProduct(*eventProduct);
}

void CatalogueController::removeEvent(std::shared_ptr<DBEvent> event)
{
    // Remove it from both repository and repository_work
    event->setRepository(impl->toWorkRepository(event->getRepository()));
    impl->m_CatalogueDao.removeEvent(*event);
    event->setRepository(impl->toSyncRepository(event->getRepository()));
    impl->m_CatalogueDao.removeEvent(*event);
}

void CatalogueController::addEvent(std::shared_ptr<DBEvent> event)
{
    event->setRepository(impl->toWorkRepository(event->getRepository()));

    auto eventTemp = *event;
    impl->m_CatalogueDao.addEvent(eventTemp);

    // Call update is necessary at the creation of add Event if it has some tags or some event
    // products
    if (!event->getEventProducts().empty() || !event->getTags().empty()) {

        auto eventProductsTemp = eventTemp.getEventProducts();
        auto eventProductTempUpdated = std::list<DBEventProduct>{};
        for (auto eventProductTemp : eventProductsTemp) {
            eventProductTemp.setEvent(eventTemp);
            eventProductTempUpdated.push_back(eventProductTemp);
        }
        eventTemp.setEventProducts(eventProductTempUpdated);

        impl->m_CatalogueDao.updateEvent(eventTemp);
    }
}

void CatalogueController::saveEvent(std::shared_ptr<DBEvent> event)
{
    impl->saveEvent(event, true);
}

std::list<std::shared_ptr<DBCatalogue> >
CatalogueController::retrieveCatalogues(const QString &repository) const
{
    QString dbDireName = repository.isEmpty() ? REPOSITORY_DEFAULT : repository;

    auto cataloguesShared = std::list<std::shared_ptr<DBCatalogue> >{};
    auto catalogues = impl->m_CatalogueDao.getCatalogues(impl->toWorkRepository(dbDireName));
    for (auto catalogue : catalogues) {
        cataloguesShared.push_back(std::make_shared<DBCatalogue>(catalogue));
    }
    return cataloguesShared;
}

void CatalogueController::updateCatalogue(std::shared_ptr<DBCatalogue> catalogue)
{
    catalogue->setRepository(impl->toWorkRepository(catalogue->getRepository()));

    impl->m_CatalogueDao.updateCatalogue(*catalogue);
}

void CatalogueController::removeCatalogue(std::shared_ptr<DBCatalogue> catalogue)
{
    // Remove it from both repository and repository_work
    catalogue->setRepository(impl->toWorkRepository(catalogue->getRepository()));
    impl->m_CatalogueDao.removeCatalogue(*catalogue);
    catalogue->setRepository(impl->toSyncRepository(catalogue->getRepository()));
    impl->m_CatalogueDao.removeCatalogue(*catalogue);
}

void CatalogueController::saveCatalogue(std::shared_ptr<DBCatalogue> catalogue)
{
    impl->saveCatalogue(catalogue, true);
}

void CatalogueController::saveAll()
{
    for (auto repository : impl->m_RepositoryList) {
        // Save Event
        auto events = this->retrieveEvents(repository);
        for (auto event : events) {
            impl->saveEvent(event, false);
        }

        // Save Catalogue
        auto catalogues = this->retrieveCatalogues(repository);
        for (auto catalogue : catalogues) {
            impl->saveCatalogue(catalogue, false);
        }
    }

    impl->savAllDB();
}

QByteArray
CatalogueController::mimeDataForEvents(const QVector<std::shared_ptr<DBEvent> > &events) const
{
    auto encodedData = QByteArray{};

    QMap<QString, QVariantList> idsPerRepository;
    for (auto event : events) {
        idsPerRepository[event->getRepository()] << event->getUniqId();
    }

    QDataStream stream{&encodedData, QIODevice::WriteOnly};
    stream << idsPerRepository;

    return encodedData;
}

QVector<std::shared_ptr<DBEvent> >
CatalogueController::eventsForMimeData(const QByteArray &mimeData) const
{
    auto events = QVector<std::shared_ptr<DBEvent> >{};
    QDataStream stream{mimeData};

    QMap<QString, QVariantList> idsPerRepository;
    stream >> idsPerRepository;

    for (auto it = idsPerRepository.cbegin(); it != idsPerRepository.cend(); ++it) {
        auto repository = it.key();
        auto allRepositoryEvent = retrieveEvents(repository);
        for (auto uuid : it.value()) {
            for (auto repositoryEvent : allRepositoryEvent) {
                if (uuid.toUuid() == repositoryEvent->getUniqId()) {
                    events << repositoryEvent;
                }
            }
        }
    }

    return events;
}

void CatalogueController::initialize()
{
    qCDebug(LOG_CatalogueController()) << tr("CatalogueController init")
                                       << QThread::currentThread();
    impl->m_WorkingMutex.lock();
    impl->m_CatalogueDao.initialize();
    auto defaultRepositoryLocation
        = QStandardPaths::writableLocation(QStandardPaths::AppDataLocation);

    QDir defaultRepositoryLocationDir;
    if (defaultRepositoryLocationDir.mkpath(defaultRepositoryLocation)) {
        defaultRepositoryLocationDir.cd(defaultRepositoryLocation);
        auto defaultRepository = defaultRepositoryLocationDir.absoluteFilePath(REPOSITORY_DEFAULT);
        qCInfo(LOG_CatalogueController()) << tr("Persistant data loading from: ")
                                          << defaultRepository;
        this->addDB(defaultRepository);
    }
    else {
        qCWarning(LOG_CatalogueController())
            << tr("Cannot load the persistent default repository from ")
            << defaultRepositoryLocation;
    }

    qCDebug(LOG_CatalogueController()) << tr("CatalogueController init END");
}

void CatalogueController::finalize()
{
    impl->m_WorkingMutex.unlock();
}

void CatalogueController::waitForFinish()
{
    QMutexLocker locker{&impl->m_WorkingMutex};
}

void CatalogueController::CatalogueControllerPrivate::copyDBtoDB(const QString &dbFrom,
                                                                 const QString &dbTo)
{
    //    auto cataloguesShared = std::list<std::shared_ptr<DBCatalogue> >{};
    auto catalogues = m_CatalogueDao.getCatalogues(dbFrom);
    auto events = m_CatalogueDao.getEvents(dbFrom);
    for (auto catalogue : catalogues) {
        m_CatalogueDao.copyCatalogue(catalogue, dbTo, true);
    }

    for (auto event : events) {
        m_CatalogueDao.copyEvent(event, dbTo, true);
    }
}

QString CatalogueController::CatalogueControllerPrivate::toWorkRepository(QString repository)
{
    auto syncRepository = toSyncRepository(repository);

    return QString("%1%2").arg(syncRepository, REPOSITORY_WORK_SUFFIX);
}

QString CatalogueController::CatalogueControllerPrivate::toSyncRepository(QString repository)
{
    auto syncRepository = repository;
    if (repository.endsWith(REPOSITORY_WORK_SUFFIX)) {
        syncRepository.remove(REPOSITORY_WORK_SUFFIX);
    }
    else if (repository.endsWith(REPOSITORY_TRASH_SUFFIX)) {
        syncRepository.remove(REPOSITORY_TRASH_SUFFIX);
    }
    return syncRepository;
}

void CatalogueController::CatalogueControllerPrivate::savAllDB()
{
    for (auto repository : m_RepositoryList) {
        auto defaultRepositoryLocation
            = QStandardPaths::writableLocation(QStandardPaths::AppDataLocation);
        m_CatalogueDao.saveDB(defaultRepositoryLocation, repository);
    }
}

void CatalogueController::CatalogueControllerPrivate::saveEvent(std::shared_ptr<DBEvent> event,
                                                                bool persist)
{
    m_CatalogueDao.copyEvent(*event, toSyncRepository(event->getRepository()), true);
    if (persist) {
        savAllDB();
    }
}

void CatalogueController::CatalogueControllerPrivate::saveCatalogue(
    std::shared_ptr<DBCatalogue> catalogue, bool persist)
{
    m_CatalogueDao.copyCatalogue(*catalogue, toSyncRepository(catalogue->getRepository()), true);
    if (persist) {
        savAllDB();
    }
}
