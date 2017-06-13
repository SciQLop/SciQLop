#include <Variable/VariableController.h>

#include <QMutex>
#include <QThread>

Q_LOGGING_CATEGORY(LOG_VariableController, "VariableController")

struct VariableController::VariableControllerPrivate {
    explicit VariableControllerPrivate()
            : m_WorkingMutex{}
    {
    }

    QMutex m_WorkingMutex;
};

VariableController::VariableController(QObject *parent)
        : QObject{parent}, impl{spimpl::make_unique_impl<VariableControllerPrivate>()}
{
    qCDebug(LOG_VariableController())
        << tr("VariableController construction") << QThread::currentThread();
}

VariableController::~VariableController()
{
    qCDebug(LOG_VariableController())
        << tr("VariableController destruction") << QThread::currentThread();
    this->waitForFinish();
}

void VariableController::initialize()
{
    qCDebug(LOG_VariableController()) << tr("VariableController init") << QThread::currentThread();
    impl->m_WorkingMutex.lock();
    qCDebug(LOG_VariableController()) << tr("VariableController init END");
}

void VariableController::finalize()
{
    impl->m_WorkingMutex.unlock();
}

void VariableController::waitForFinish()
{
    QMutexLocker locker{&impl->m_WorkingMutex};
}
