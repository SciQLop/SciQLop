#include <Catalogue/CatalogueController.h>

#include <Variable/Variable.h>

#include <CatalogueDao.h>

#include <QMutex>
#include <QThread>

#include <QDir>
#include <QStandardPaths>

Q_LOGGING_CATEGORY(LOG_CatalogueController, "CatalogueController")

class CatalogueController::CatalogueControllerPrivate {
public:
    QMutex m_WorkingMutex;
    CatalogueDao m_CatalogueDao;
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

void CatalogueController::initialize()
{
    qCDebug(LOG_CatalogueController()) << tr("CatalogueController init")
                                       << QThread::currentThread();
    impl->m_WorkingMutex.lock();
    impl->m_CatalogueDao.initialize();
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
