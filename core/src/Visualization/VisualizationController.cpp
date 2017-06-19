#include <Visualization/VisualizationController.h>

#include <Variable/Variable.h>

#include <QMutex>
#include <QThread>

#include <QDir>
#include <QStandardPaths>

Q_LOGGING_CATEGORY(LOG_VisualizationController, "VisualizationController")

class VisualizationController::VisualizationControllerPrivate {
public:
    QMutex m_WorkingMutex;
};

VisualizationController::VisualizationController(QObject *parent)
        : impl{spimpl::make_unique_impl<VisualizationControllerPrivate>()}
{
    qCDebug(LOG_VisualizationController()) << tr("VisualizationController construction")
                                           << QThread::currentThread();
}

VisualizationController::~VisualizationController()
{
    qCDebug(LOG_VisualizationController()) << tr("VisualizationController destruction")
                                           << QThread::currentThread();
    this->waitForFinish();
}

void VisualizationController::initialize()
{
    qCDebug(LOG_VisualizationController()) << tr("VisualizationController init")
                                           << QThread::currentThread();
    impl->m_WorkingMutex.lock();
    qCDebug(LOG_VisualizationController()) << tr("VisualizationController init END");
}

void VisualizationController::finalize()
{
    impl->m_WorkingMutex.unlock();
}

void VisualizationController::waitForFinish()
{
    QMutexLocker locker{&impl->m_WorkingMutex};
}
