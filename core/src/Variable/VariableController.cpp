#include <Variable/VariableController.h>
#include <Variable/VariableModel.h>

#include <Data/DataProviderParameters.h>
#include <Data/IDataProvider.h>
#include <Data/IDataSeries.h>

#include <QDateTime>
#include <QMutex>
#include <QThread>

Q_LOGGING_CATEGORY(LOG_VariableController, "VariableController")

namespace {

/// @todo Generates default dataseries, according to the provider passed in parameter. This method
/// will be deleted when the timerange is recovered from SciQlop
std::unique_ptr<IDataSeries> generateDefaultDataSeries(const IDataProvider &provider) noexcept
{
    auto parameters = DataProviderParameters{
        static_cast<double>(QDateTime{QDate{2017, 01, 01}}.toSecsSinceEpoch()),
        static_cast<double>(QDateTime{QDate{2017, 01, 03}}.toSecsSinceEpoch())};

    return provider.retrieveData(parameters);
}

} // namespace

struct VariableController::VariableControllerPrivate {
    explicit VariableControllerPrivate(VariableController *parent)
            : m_WorkingMutex{}, m_VariableModel{new VariableModel{parent}}
    {
    }

    QMutex m_WorkingMutex;
    /// Variable model. The VariableController has the ownership
    VariableModel *m_VariableModel;
};

VariableController::VariableController(QObject *parent)
        : QObject{parent}, impl{spimpl::make_unique_impl<VariableControllerPrivate>(this)}
{
    qCDebug(LOG_VariableController()) << tr("VariableController construction")
                                      << QThread::currentThread();
}

VariableController::~VariableController()
{
    qCDebug(LOG_VariableController()) << tr("VariableController destruction")
                                      << QThread::currentThread();
    this->waitForFinish();
}

VariableModel *VariableController::variableModel() noexcept
{
    return impl->m_VariableModel;
}

void VariableController::createVariable(const QString &name,
                                        std::shared_ptr<IDataProvider> provider) noexcept
{
    /// @todo : for the moment :
    /// - the provider is only used to retrieve data from the variable for its initialization, but
    /// it will be retained later
    /// - default data are generated for the variable, without taking into account the timerange set
    /// in sciqlop
    if (auto newVariable
        = impl->m_VariableModel->createVariable(name, generateDefaultDataSeries(*provider))) {
        emit variableCreated(newVariable);
    }
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
