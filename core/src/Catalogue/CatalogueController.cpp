#include <Catalogue/CatalogueController.h>

#include <Variable/Variable.h>

#include <CatalogueDao.h>

#include <ComparaisonPredicate.h>
#include <CompoundPredicate.h>
#include <DBCatalogue.h>
#include <DBEvent.h>
#include <DBTag.h>
#include <IRequestPredicate.h>

#include <QMutex>
#include <QThread>

#include <QDir>
#include <QStandardPaths>

Q_LOGGING_CATEGORY(LOG_CatalogueController, "CatalogueController")

namespace {

static QString REPOSITORY_WORK_SUFFIX = QString{"Work"};

}

class CatalogueController::CatalogueControllerPrivate {
public:
    QMutex m_WorkingMutex;
    CatalogueDao m_CatalogueDao;

    std::list<QString> m_RepositoryList;
};

CatalogueController::CatalogueController(QObject *parent)
        : impl{spimpl::make_unique_impl<CatalogueControllerPrivate>()}
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
            impl->m_RepositoryList.push_back(dirName);
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
    auto eventsShared = std::list<std::shared_ptr<DBEvent> >{};
    auto events = impl->m_CatalogueDao.getEvents(repository);
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
CatalogueController::retrieveEventsFromCatalogue(const QString &repository,
                                                 std::shared_ptr<DBCatalogue> catalogue) const
{
    auto eventsShared = std::list<std::shared_ptr<DBEvent> >{};
    auto events = impl->m_CatalogueDao.getCatalogueEvents(*catalogue);
    for (auto event : events) {
        eventsShared.push_back(std::make_shared<DBEvent>(event));
    }
    return eventsShared;
}

std::list<std::shared_ptr<DBCatalogue> >
CatalogueController::getCatalogues(const QString &repository) const
{
    auto cataloguesShared = std::list<std::shared_ptr<DBCatalogue> >{};
    auto catalogues = impl->m_CatalogueDao.getCatalogues(repository);
    for (auto catalogue : catalogues) {
        cataloguesShared.push_back(std::make_shared<DBCatalogue>(catalogue));
    }
    return cataloguesShared;
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
        qCInfo(LOG_CatalogueController())
            << tr("Persistant data loading from: ") << defaultRepository;
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
