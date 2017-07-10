#include <Variable/Variable.h>
#include <Variable/VariableCacheController.h>
#include <Variable/VariableController.h>
#include <Variable/VariableModel.h>

#include <Data/DataProviderParameters.h>
#include <Data/IDataProvider.h>
#include <Data/IDataSeries.h>
#include <Time/TimeController.h>

#include <QDateTime>
#include <QMutex>
#include <QThread>
#include <QUuid>
#include <QtCore/QItemSelectionModel>

#include <unordered_map>

Q_LOGGING_CATEGORY(LOG_VariableController, "VariableController")

struct VariableController::VariableControllerPrivate {
    explicit VariableControllerPrivate(VariableController *parent)
            : m_WorkingMutex{},
              m_VariableModel{new VariableModel{parent}},
              m_VariableSelectionModel{new QItemSelectionModel{m_VariableModel, parent}},
              m_VariableCacheController{std::make_unique<VariableCacheController>()}
    {
    }

    QMutex m_WorkingMutex;
    /// Variable model. The VariableController has the ownership
    VariableModel *m_VariableModel;
    QItemSelectionModel *m_VariableSelectionModel;


    TimeController *m_TimeController{nullptr};
    std::unique_ptr<VariableCacheController> m_VariableCacheController;

    std::unordered_map<std::shared_ptr<Variable>, std::shared_ptr<IDataProvider> >
        m_VariableToProviderMap;
    std::unordered_map<std::shared_ptr<Variable>, QUuid> m_VariableToToken;
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

QItemSelectionModel *VariableController::variableSelectionModel() noexcept
{
    return impl->m_VariableSelectionModel;
}

void VariableController::setTimeController(TimeController *timeController) noexcept
{
    impl->m_TimeController = timeController;
}

void VariableController::deleteVariable(std::shared_ptr<Variable> variable) noexcept
{
    if (!variable) {
        qCCritical(LOG_VariableController()) << "Can't delete variable: variable is null";
        return;
    }

    // Spreads in SciQlop that the variable will be deleted, so that potential receivers can
    // make some treatments before the deletion
    emit variableAboutToBeDeleted(variable);

    // Deletes provider
    auto nbProvidersDeleted = impl->m_VariableToProviderMap.erase(variable);
    qCDebug(LOG_VariableController())
        << tr("Number of providers deleted for variable %1: %2")
               .arg(variable->name(), QString::number(nbProvidersDeleted));

    // Clears cache
    impl->m_VariableCacheController->clear(variable);

    // Deletes from model
    impl->m_VariableModel->deleteVariable(variable);
}

void VariableController::deleteVariables(
    const QVector<std::shared_ptr<Variable> > &variables) noexcept
{
    for (auto variable : qAsConst(variables)) {
        deleteVariable(variable);
    }
}

void VariableController::createVariable(const QString &name,
                                        std::shared_ptr<IDataProvider> provider) noexcept
{

    if (!impl->m_TimeController) {
        qCCritical(LOG_VariableController())
            << tr("Impossible to create variable: The time controller is null");
        return;
    }


    /// @todo : for the moment :
    /// - the provider is only used to retrieve data from the variable for its initialization, but
    /// it will be retained later
    /// - default data are generated for the variable, without taking into account the timerange set
    /// in sciqlop
    auto dateTime = impl->m_TimeController->dateTime();
    if (auto newVariable = impl->m_VariableModel->createVariable(name, dateTime)) {
        auto token = QUuid::createUuid();

        // store the provider
        impl->m_VariableToProviderMap[newVariable] = provider;
        impl->m_VariableToToken[newVariable] = token;

        auto addDateTimeAcquired = [ this, varW = std::weak_ptr<Variable>{newVariable} ](
            QUuid token, auto dataSeriesAcquired, auto dateTimeToPutInCache)
        {
            if (auto variable = varW.lock()) {
                auto varToken = impl->m_VariableToToken.at(variable);
                if (varToken == token) {
                    impl->m_VariableCacheController->addDateTime(variable, dateTimeToPutInCache);
                    variable->setDataSeries(dataSeriesAcquired);
                }
            }
        };

        connect(provider.get(), &IDataProvider::dataProvided, addDateTimeAcquired);
        this->onRequestDataLoading(newVariable, dateTime);
    }
}

void VariableController::onDateTimeOnSelection(const SqpDateTime &dateTime)
{
    qCDebug(LOG_VariableController()) << "VariableController::onDateTimeOnSelection"
                                      << QThread::currentThread()->objectName();
    auto selectedRows = impl->m_VariableSelectionModel->selectedRows();

    for (const auto &selectedRow : qAsConst(selectedRows)) {
        if (auto selectedVariable = impl->m_VariableModel->variable(selectedRow.row())) {
            selectedVariable->setDateTime(dateTime);
            this->onRequestDataLoading(selectedVariable, dateTime);
        }
    }
}


void VariableController::onRequestDataLoading(std::shared_ptr<Variable> variable,
                                              const SqpDateTime &dateTime)
{
    qCDebug(LOG_VariableController()) << "VariableController::onRequestDataLoading"
                                      << QThread::currentThread()->objectName();
    // we want to load data of the variable for the dateTime.
    // First we check if the cache contains some of them.
    // For the other, we ask the provider to give them.
    if (variable) {

        auto dateTimeListNotInCache
            = impl->m_VariableCacheController->provideNotInCacheDateTimeList(variable, dateTime);

        if (!dateTimeListNotInCache.empty()) {
            // Ask the provider for each data on the dateTimeListNotInCache
            auto token = impl->m_VariableToToken.at(variable);
            impl->m_VariableToProviderMap.at(variable)->requestDataLoading(
                token, std::move(dateTimeListNotInCache));
        }
        else {
            emit variable->updated();
        }
    }
    else {
        qCCritical(LOG_VariableController()) << tr("Impossible to load data of a variable null");
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
