#include <Variable/Variable.h>
#include <Variable/VariableAcquisitionWorker.h>
#include <Variable/VariableCacheStrategy.h>
#include <Variable/VariableCacheStrategyFactory.h>
#include <Variable/VariableController.h>
#include <Variable/VariableModel.h>
#include <Variable/VariableSynchronizationGroup.h>

#include <Data/DataProviderParameters.h>
#include <Data/IDataProvider.h>
#include <Data/IDataSeries.h>
#include <Data/VariableRequest.h>
#include <Time/TimeController.h>

#include <Common/Numeric.h>

#include <QDataStream>
#include <QMutex>
#include <QThread>
#include <QUuid>
#include <QtCore/QItemSelectionModel>

#include <deque>
#include <set>
#include <unordered_map>

Q_LOGGING_CATEGORY(LOG_VariableController, "VariableController")

namespace {

DateTimeRange computeSynchroRangeRequested(const DateTimeRange &varRange, const DateTimeRange &graphRange,
                                      const DateTimeRange &oldGraphRange)
{
    auto zoomType = VariableController::getZoomType(graphRange, oldGraphRange);

    auto varRangeRequested = varRange;
    switch (zoomType) {
        case AcquisitionZoomType::ZoomIn: {
            auto deltaLeft = graphRange.m_TStart - oldGraphRange.m_TStart;
            auto deltaRight = oldGraphRange.m_TEnd - graphRange.m_TEnd;
            varRangeRequested.m_TStart += deltaLeft;
            varRangeRequested.m_TEnd -= deltaRight;
            break;
        }

        case AcquisitionZoomType::ZoomOut: {
            auto deltaLeft = oldGraphRange.m_TStart - graphRange.m_TStart;
            auto deltaRight = graphRange.m_TEnd - oldGraphRange.m_TEnd;
            varRangeRequested.m_TStart -= deltaLeft;
            varRangeRequested.m_TEnd += deltaRight;
            break;
        }
        case AcquisitionZoomType::PanRight: {
            auto deltaLeft = graphRange.m_TStart - oldGraphRange.m_TStart;
            auto deltaRight = graphRange.m_TEnd - oldGraphRange.m_TEnd;
            varRangeRequested.m_TStart += deltaLeft;
            varRangeRequested.m_TEnd += deltaRight;
            break;
        }
        case AcquisitionZoomType::PanLeft: {
            auto deltaLeft = oldGraphRange.m_TStart - graphRange.m_TStart;
            auto deltaRight = oldGraphRange.m_TEnd - graphRange.m_TEnd;
            varRangeRequested.m_TStart -= deltaLeft;
            varRangeRequested.m_TEnd -= deltaRight;
            break;
        }
        case AcquisitionZoomType::Unknown: {
            qCCritical(LOG_VariableController())
                << VariableController::tr("Impossible to synchronize: zoom type unknown");
            break;
        }
        default:
            qCCritical(LOG_VariableController()) << VariableController::tr(
                "Impossible to synchronize: zoom type not take into account");
            // No action
            break;
    }

    return varRangeRequested;
}
}

enum class VariableRequestHandlerState { OFF, RUNNING, PENDING };

struct VariableRequestHandler {

    VariableRequestHandler()
    {
        m_CanUpdate = false;
        m_State = VariableRequestHandlerState::OFF;
    }

    QUuid m_VarId;
    VariableRequest m_RunningVarRequest;
    VariableRequest m_PendingVarRequest;
    VariableRequestHandlerState m_State;
    bool m_CanUpdate;
};

struct VariableController::VariableControllerPrivate {
    explicit VariableControllerPrivate(VariableController *parent)
            : m_WorkingMutex{},
              m_VariableModel{new VariableModel{parent}},
              m_VariableSelectionModel{new QItemSelectionModel{m_VariableModel, parent}},
              // m_VariableCacheStrategy{std::make_unique<VariableCacheStrategy>()},
              m_VariableCacheStrategy{VariableCacheStrategyFactory::createCacheStrategy(
                  CacheStrategy::SingleThreshold)},
              m_VariableAcquisitionWorker{std::make_unique<VariableAcquisitionWorker>()},
              q{parent}
    {

        m_VariableAcquisitionWorker->moveToThread(&m_VariableAcquisitionWorkerThread);
        m_VariableAcquisitionWorkerThread.setObjectName("VariableAcquisitionWorkerThread");
    }


    virtual ~VariableControllerPrivate()
    {
        qCDebug(LOG_VariableController()) << tr("VariableControllerPrivate destruction");
        m_VariableAcquisitionWorkerThread.quit();
        m_VariableAcquisitionWorkerThread.wait();
    }


    void processRequest(std::shared_ptr<Variable> var, const DateTimeRange &rangeRequested,
                        QUuid varRequestId);

    std::shared_ptr<Variable> findVariable(QUuid vIdentifier);
    std::shared_ptr<IDataSeries>
    retrieveDataSeries(const QVector<AcquisitionDataPacket> acqDataPacketVector);

    void registerProvider(std::shared_ptr<IDataProvider> provider);

    void storeVariableRequest(QUuid varId, QUuid varRequestId, const VariableRequest &varRequest);
    QUuid acceptVariableRequest(QUuid varId, std::shared_ptr<IDataSeries> dataSeries);
    void updateVariables(QUuid varRequestId);
    void updateVariableRequest(QUuid varRequestId);
    void cancelVariableRequest(QUuid varRequestId);
    void executeVarRequest(std::shared_ptr<Variable> var, VariableRequest &varRequest);
    bool hasPendingDownloads();
    template <typename VariableIterator>
    void desynchronize(VariableIterator variableIt, const QUuid &syncGroupId);

    QMutex m_WorkingMutex;
    /// Variable model. The VariableController has the ownership
    VariableModel *m_VariableModel;
    QItemSelectionModel *m_VariableSelectionModel;


    std::unique_ptr<VariableCacheStrategy> m_VariableCacheStrategy;
    std::unique_ptr<VariableAcquisitionWorker> m_VariableAcquisitionWorker;
    QThread m_VariableAcquisitionWorkerThread;

    std::unordered_map<std::shared_ptr<Variable>, std::shared_ptr<IDataProvider> >
        m_VariableToProviderMap;
    std::unordered_map<std::shared_ptr<Variable>, QUuid> m_VariableToIdentifierMap;
    std::map<QUuid, std::shared_ptr<VariableSynchronizationGroup> >
        m_GroupIdToVariableSynchronizationGroupMap;
    std::map<QUuid, QUuid> m_VariableIdGroupIdMap;
    std::set<std::shared_ptr<IDataProvider> > m_ProviderSet;

    std::map<QUuid, std::list<QUuid> > m_VarGroupIdToVarIds;
    std::map<QUuid, std::unique_ptr<VariableRequestHandler> > m_VarIdToVarRequestHandler;

    VariableController *q;
};


VariableController::VariableController(QObject *parent)
        : QObject{parent}, impl{spimpl::make_unique_impl<VariableControllerPrivate>(this)}
{
    qCDebug(LOG_VariableController()) << tr("VariableController construction")
                                      << QThread::currentThread();

    connect(impl->m_VariableModel, &VariableModel::abortProgessRequested, this,
            &VariableController::onAbortProgressRequested);

    connect(impl->m_VariableAcquisitionWorker.get(),
            &VariableAcquisitionWorker::variableCanceledRequested, this,
            &VariableController::onAbortAcquisitionRequested);

    connect(impl->m_VariableAcquisitionWorker.get(), &VariableAcquisitionWorker::dataProvided, this,
            &VariableController::onDataProvided);
    connect(impl->m_VariableAcquisitionWorker.get(),
            &VariableAcquisitionWorker::variableRequestInProgress, this,
            &VariableController::onVariableRetrieveDataInProgress);


    connect(&impl->m_VariableAcquisitionWorkerThread, &QThread::started,
            impl->m_VariableAcquisitionWorker.get(), &VariableAcquisitionWorker::initialize);
    connect(&impl->m_VariableAcquisitionWorkerThread, &QThread::finished,
            impl->m_VariableAcquisitionWorker.get(), &VariableAcquisitionWorker::finalize);

    connect(impl->m_VariableModel, &VariableModel::requestVariableRangeUpdate, this,
            &VariableController::onUpdateDateTime);

    impl->m_VariableAcquisitionWorkerThread.start();
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

std::shared_ptr<Variable>
VariableController::cloneVariable(std::shared_ptr<Variable> variable) noexcept
{
    if (impl->m_VariableModel->containsVariable(variable)) {
        // Clones variable
        auto duplicate = variable->clone();

        // Adds clone to model
        impl->m_VariableModel->addVariable(duplicate);

        // Generates clone identifier
        impl->m_VariableToIdentifierMap[duplicate] = QUuid::createUuid();

        // Registers provider
        auto variableProvider = impl->m_VariableToProviderMap.at(variable);
        auto duplicateProvider = variableProvider != nullptr ? variableProvider->clone() : nullptr;

        impl->m_VariableToProviderMap[duplicate] = duplicateProvider;
        if (duplicateProvider) {
            impl->registerProvider(duplicateProvider);
        }

        return duplicate;
    }
    else {
        qCCritical(LOG_VariableController())
            << tr("Can't create duplicate of variable %1: variable not registered in the model")
                   .arg(variable->name());
        return nullptr;
    }
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

    auto variableIt = impl->m_VariableToIdentifierMap.find(variable);
    Q_ASSERT(variableIt != impl->m_VariableToIdentifierMap.cend());

    auto variableId = variableIt->second;

    // Removes variable's handler
    impl->m_VarIdToVarRequestHandler.erase(variableId);

    // Desynchronizes variable (if the variable is in a sync group)
    auto syncGroupIt = impl->m_VariableIdGroupIdMap.find(variableId);
    if (syncGroupIt != impl->m_VariableIdGroupIdMap.cend()) {
        impl->desynchronize(variableIt, syncGroupIt->second);
    }

    // Deletes identifier
    impl->m_VariableToIdentifierMap.erase(variableIt);

    // Deletes provider
    auto nbProvidersDeleted = impl->m_VariableToProviderMap.erase(variable);
    qCDebug(LOG_VariableController())
        << tr("Number of providers deleted for variable %1: %2")
               .arg(variable->name(), QString::number(nbProvidersDeleted));


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

QByteArray
VariableController::mimeDataForVariables(const QList<std::shared_ptr<Variable> > &variables) const
{
    auto encodedData = QByteArray{};

    QVariantList ids;
    for (auto &var : variables) {
        auto itVar = impl->m_VariableToIdentifierMap.find(var);
        if (itVar == impl->m_VariableToIdentifierMap.cend()) {
            qCCritical(LOG_VariableController())
                << tr("Impossible to find the data for an unknown variable.");
        }

        ids << itVar->second.toByteArray();
    }

    QDataStream stream{&encodedData, QIODevice::WriteOnly};
    stream << ids;

    return encodedData;
}

QList<std::shared_ptr<Variable> >
VariableController::variablesForMimeData(const QByteArray &mimeData) const
{
    auto variables = QList<std::shared_ptr<Variable> >{};
    QDataStream stream{mimeData};

    QVariantList ids;
    stream >> ids;

    for (auto id : ids) {
        auto uuid = QUuid{id.toByteArray()};
        auto var = impl->findVariable(uuid);
        variables << var;
    }

    return variables;
}

std::shared_ptr<Variable>
VariableController::createVariable(const QString &name, const QVariantHash &metadata,
                                   std::shared_ptr<IDataProvider> provider, const DateTimeRange& range) noexcept
{
//    if (!impl->m_TimeController) {
//        qCCritical(LOG_VariableController())
//            << tr("Impossible to create variable: The time controller is null");
//        return nullptr;
//    }

//    auto range = impl->m_TimeController->dateTime();

    if (auto newVariable = impl->m_VariableModel->createVariable(name, metadata)) {
        auto varId = QUuid::createUuid();

        // Create the handler
        auto varRequestHandler = std::make_unique<VariableRequestHandler>();
        varRequestHandler->m_VarId = varId;

        impl->m_VarIdToVarRequestHandler.insert(
            std::make_pair(varId, std::move(varRequestHandler)));

        // store the provider
        impl->registerProvider(provider);

        // Associate the provider
        impl->m_VariableToProviderMap[newVariable] = provider;
        impl->m_VariableToIdentifierMap[newVariable] = varId;

        this->onRequestDataLoading(QVector<std::shared_ptr<Variable> >{newVariable}, range, false);

        //        auto varRequestId = QUuid::createUuid();
        //        qCInfo(LOG_VariableController()) << "createVariable: " << varId << varRequestId;
        //        impl->processRequest(newVariable, range, varRequestId);
        //        impl->updateVariableRequest(varRequestId);

        emit variableAdded(newVariable);

        return newVariable;
    }

    qCCritical(LOG_VariableController()) << tr("Impossible to create variable");
    return nullptr;
}

void VariableController::onDateTimeOnSelection(const DateTimeRange &dateTime)
{
    // NOTE: Even if acquisition request is aborting, the graphe range will be changed
    qCDebug(LOG_VariableController()) << "VariableController::onDateTimeOnSelection"
                                      << QThread::currentThread()->objectName();
    auto selectedRows = impl->m_VariableSelectionModel->selectedRows();

    // NOTE we only permit the time modification for one variable
    // DEPRECATED
    // auto variables = QVector<std::shared_ptr<Variable> >{};
    //        for (const auto &selectedRow : qAsConst(selectedRows)) {
    //            if (auto selectedVariable =
    //            impl->m_VariableModel->variable(selectedRow.row())) {
    //                variables << selectedVariable;

    //                // notify that rescale operation has to be done
    //                emit rangeChanged(selectedVariable, dateTime);
    //            }
    //        }
    //        if (!variables.isEmpty()) {
    //            this->onRequestDataLoading(variables, dateTime, synchro);
    //        }
    if (selectedRows.size() == 1) {

        if (auto selectedVariable
            = impl->m_VariableModel->variable(qAsConst(selectedRows).first().row())) {

            onUpdateDateTime(selectedVariable, dateTime);
        }
    }
    else if (selectedRows.size() > 1) {
        qCCritical(LOG_VariableController())
            << tr("Impossible to set time for more than 1 variable in the same time");
    }
    else {
        qCWarning(LOG_VariableController())
            << tr("There is no variable selected to set the time one");
    }
}

void VariableController::onUpdateDateTime(std::shared_ptr<Variable> variable,
                                          const DateTimeRange &dateTime)
{
    auto itVar = impl->m_VariableToIdentifierMap.find(variable);
    if (itVar == impl->m_VariableToIdentifierMap.cend()) {
        qCCritical(LOG_VariableController())
            << tr("Impossible to onDateTimeOnSelection request for unknown variable");
        return;
    }

    // notify that rescale operation has to be done
    emit rangeChanged(variable, dateTime);

    auto synchro
        = impl->m_VariableIdGroupIdMap.find(itVar->second) != impl->m_VariableIdGroupIdMap.cend();

    this->onRequestDataLoading(QVector<std::shared_ptr<Variable> >{variable}, dateTime, synchro);
}

void VariableController::onDataProvided(QUuid vIdentifier, const DateTimeRange &rangeRequested,
                                        const DateTimeRange &cacheRangeRequested,
                                        QVector<AcquisitionDataPacket> dataAcquired)
{
    qCDebug(LOG_VariableController()) << tr("onDataProvided") << QThread::currentThread();
    auto retrievedDataSeries = impl->retrieveDataSeries(dataAcquired);
    auto varRequestId = impl->acceptVariableRequest(vIdentifier, retrievedDataSeries);
    if (!varRequestId.isNull()) {
        impl->updateVariables(varRequestId);
    }
}

void VariableController::onVariableRetrieveDataInProgress(QUuid identifier, double progress)
{
    qCDebug(LOG_VariableController())
        << "TORM: variableController::onVariableRetrieveDataInProgress"
        << QThread::currentThread()->objectName() << progress;
    if (auto var = impl->findVariable(identifier)) {
        impl->m_VariableModel->setDataProgress(var, progress);
    }
    else {
        qCCritical(LOG_VariableController())
            << tr("Impossible to notify progression of a null variable");
    }
}

void VariableController::onAbortProgressRequested(std::shared_ptr<Variable> variable)
{
    qCDebug(LOG_VariableController()) << "TORM: variableController::onAbortProgressRequested"
                                      << QThread::currentThread()->objectName() << variable->name();

    auto itVar = impl->m_VariableToIdentifierMap.find(variable);
    if (itVar == impl->m_VariableToIdentifierMap.cend()) {
        qCCritical(LOG_VariableController())
            << tr("Impossible to onAbortProgressRequested request for unknown variable");
        return;
    }

    auto varId = itVar->second;

    auto itVarHandler = impl->m_VarIdToVarRequestHandler.find(varId);
    if (itVarHandler == impl->m_VarIdToVarRequestHandler.cend()) {
        qCCritical(LOG_VariableController())
            << tr("Impossible to onAbortProgressRequested for variable with unknown handler");
        return;
    }

    auto varHandler = itVarHandler->second.get();

    // case where a variable has a running request
    if (varHandler->m_State != VariableRequestHandlerState::OFF) {
        impl->cancelVariableRequest(varHandler->m_RunningVarRequest.m_VariableGroupId);
    }
}

void VariableController::onAbortAcquisitionRequested(QUuid vIdentifier)
{
    qCDebug(LOG_VariableController()) << "TORM: variableController::onAbortAcquisitionRequested"
                                      << QThread::currentThread()->objectName() << vIdentifier;

    if (auto var = impl->findVariable(vIdentifier)) {
        this->onAbortProgressRequested(var);
    }
    else {
        qCCritical(LOG_VariableController())
            << tr("Impossible to abort Acquisition Requestof a null variable");
    }
}

void VariableController::onAddSynchronizationGroupId(QUuid synchronizationGroupId)
{
    qCDebug(LOG_VariableController()) << "TORM: VariableController::onAddSynchronizationGroupId"
                                      << QThread::currentThread()->objectName()
                                      << synchronizationGroupId;
    auto vSynchroGroup = std::make_shared<VariableSynchronizationGroup>();
    impl->m_GroupIdToVariableSynchronizationGroupMap.insert(
        std::make_pair(synchronizationGroupId, vSynchroGroup));
}

void VariableController::onRemoveSynchronizationGroupId(QUuid synchronizationGroupId)
{
    impl->m_GroupIdToVariableSynchronizationGroupMap.erase(synchronizationGroupId);
}

void VariableController::onAddSynchronized(std::shared_ptr<Variable> variable,
                                           QUuid synchronizationGroupId)

{
    qCDebug(LOG_VariableController()) << "TORM: VariableController::onAddSynchronized"
                                      << synchronizationGroupId;
    auto varToVarIdIt = impl->m_VariableToIdentifierMap.find(variable);
    if (varToVarIdIt != impl->m_VariableToIdentifierMap.cend()) {
        auto groupIdToVSGIt
            = impl->m_GroupIdToVariableSynchronizationGroupMap.find(synchronizationGroupId);
        if (groupIdToVSGIt != impl->m_GroupIdToVariableSynchronizationGroupMap.cend()) {
            impl->m_VariableIdGroupIdMap.insert(
                std::make_pair(varToVarIdIt->second, synchronizationGroupId));
            groupIdToVSGIt->second->addVariable(varToVarIdIt->second);
        }
        else {
            qCCritical(LOG_VariableController())
                << tr("Impossible to synchronize a variable with an unknown sycnhronization group")
                << variable->name();
        }
    }
    else {
        qCCritical(LOG_VariableController())
            << tr("Impossible to synchronize a variable with no identifier") << variable->name();
    }
}

void VariableController::desynchronize(std::shared_ptr<Variable> variable,
                                       QUuid synchronizationGroupId)
{
    // Gets variable id
    auto variableIt = impl->m_VariableToIdentifierMap.find(variable);
    if (variableIt == impl->m_VariableToIdentifierMap.cend()) {
        qCCritical(LOG_VariableController())
            << tr("Can't desynchronize variable %1: variable identifier not found")
                   .arg(variable->name());
        return;
    }

    impl->desynchronize(variableIt, synchronizationGroupId);
}

void VariableController::onRequestDataLoading(QVector<std::shared_ptr<Variable> > variables,
                                              const DateTimeRange &range, bool synchronise)
{
    // variables is assumed synchronized
    // TODO: Asser variables synchronization
    // we want to load data of the variable for the dateTime.
    if (variables.isEmpty()) {
        return;
    }

    auto varRequestId = QUuid::createUuid();
    qCDebug(LOG_VariableController()) << "VariableController::onRequestDataLoading"
                                      << QThread::currentThread()->objectName() << varRequestId
                                      << range << synchronise;

    if (!synchronise) {
        auto varIds = std::list<QUuid>{};
        for (const auto &var : variables) {
            auto vId = impl->m_VariableToIdentifierMap.at(var);
            varIds.push_back(vId);
        }
        impl->m_VarGroupIdToVarIds.insert(std::make_pair(varRequestId, varIds));
        for (const auto &var : variables) {
            qCDebug(LOG_VariableController()) << "processRequest for" << var->name() << varRequestId
                                              << varIds.size();
            impl->processRequest(var, range, varRequestId);
        }
    }
    else {
        auto vId = impl->m_VariableToIdentifierMap.at(variables.first());
        auto varIdToGroupIdIt = impl->m_VariableIdGroupIdMap.find(vId);
        if (varIdToGroupIdIt != impl->m_VariableIdGroupIdMap.cend()) {
            auto groupId = varIdToGroupIdIt->second;

            auto vSynchronizationGroup
                = impl->m_GroupIdToVariableSynchronizationGroupMap.at(groupId);
            auto vSyncIds = vSynchronizationGroup->getIds();

            auto varIds = std::list<QUuid>{};
            for (auto vId : vSyncIds) {
                varIds.push_back(vId);
            }
            impl->m_VarGroupIdToVarIds.insert(std::make_pair(varRequestId, varIds));

            for (auto vId : vSyncIds) {
                auto var = impl->findVariable(vId);

                // Don't process already processed var
                if (var != nullptr) {
                    qCDebug(LOG_VariableController()) << "processRequest synchro for" << var->name()
                                                      << varRequestId;
                    auto vSyncRangeRequested
                        = variables.contains(var)
                              ? range
                              : computeSynchroRangeRequested(var->range(), range,
                                                             variables.first()->range());
                    qCDebug(LOG_VariableController()) << "synchro RR" << vSyncRangeRequested;
                    impl->processRequest(var, vSyncRangeRequested, varRequestId);
                }
                else {
                    qCCritical(LOG_VariableController())

                        << tr("Impossible to synchronize a null variable");
                }
            }
        }
    }

    impl->updateVariables(varRequestId);
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

bool VariableController::hasPendingDownloads()
{
    return impl->hasPendingDownloads();
}

AcquisitionZoomType VariableController::getZoomType(const DateTimeRange &range, const DateTimeRange &oldRange)
{
    if (almost_equal(range.delta(), oldRange.delta(), 1)) // same delta -> must be a pan or nothing
    {
        if(range.m_TStart > oldRange.m_TStart)
            return AcquisitionZoomType::PanRight;
        if(range.m_TStart < oldRange.m_TStart)
            return AcquisitionZoomType::PanLeft;
    }
    else // different delta -> must be a zoom
    {
        if(range.m_TStart > oldRange.m_TStart)
            return AcquisitionZoomType::ZoomIn;
        if(range.m_TStart < oldRange.m_TStart)
            return AcquisitionZoomType::ZoomOut;
    }
    return AcquisitionZoomType::Unknown;
}

void VariableController::VariableControllerPrivate::processRequest(std::shared_ptr<Variable> var,
                                                                   const DateTimeRange &rangeRequested,
                                                                   QUuid varRequestId)
{
    auto itVar = m_VariableToIdentifierMap.find(var);
    if (itVar == m_VariableToIdentifierMap.cend()) {
        qCCritical(LOG_VariableController())
            << tr("Impossible to process request for unknown variable");
        return;
    }

    auto varId = itVar->second;

    auto itVarHandler = m_VarIdToVarRequestHandler.find(varId);
    if (itVarHandler == m_VarIdToVarRequestHandler.cend()) {
        qCCritical(LOG_VariableController())
            << tr("Impossible to process request for variable with unknown handler");
        return;
    }

    auto oldRange = var->range();

    auto varHandler = itVarHandler->second.get();

    if (varHandler->m_State != VariableRequestHandlerState::OFF) {
        oldRange = varHandler->m_RunningVarRequest.m_RangeRequested;
    }

    auto varRequest = VariableRequest{};
    varRequest.m_VariableGroupId = varRequestId;
    auto varStrategyRangesRequested
        = m_VariableCacheStrategy->computeRange(oldRange, rangeRequested);
    varRequest.m_RangeRequested = varStrategyRangesRequested.first;
    varRequest.m_CacheRangeRequested = varStrategyRangesRequested.second;

    switch (varHandler->m_State) {
        case VariableRequestHandlerState::OFF: {
            qCDebug(LOG_VariableController()) << tr("Process Request OFF")
                                              << varRequest.m_RangeRequested
                                              << varRequest.m_CacheRangeRequested;
            varHandler->m_RunningVarRequest = varRequest;
            varHandler->m_State = VariableRequestHandlerState::RUNNING;
            executeVarRequest(var, varRequest);
            break;
        }
        case VariableRequestHandlerState::RUNNING: {
            qCDebug(LOG_VariableController()) << tr("Process Request RUNNING")
                                              << varRequest.m_RangeRequested
                                              << varRequest.m_CacheRangeRequested;
            varHandler->m_State = VariableRequestHandlerState::PENDING;
            varHandler->m_PendingVarRequest = varRequest;
            break;
        }
        case VariableRequestHandlerState::PENDING: {
            qCDebug(LOG_VariableController()) << tr("Process Request PENDING")
                                              << varRequest.m_RangeRequested
                                              << varRequest.m_CacheRangeRequested;
            auto variableGroupIdToCancel = varHandler->m_PendingVarRequest.m_VariableGroupId;
            cancelVariableRequest(variableGroupIdToCancel);
            // Cancel variable can make state downgrade
            varHandler->m_State = VariableRequestHandlerState::PENDING;
            varHandler->m_PendingVarRequest = varRequest;

            break;
        }
        default:
            qCCritical(LOG_VariableController())
                << QObject::tr("Unknown VariableRequestHandlerState");
    }
}

std::shared_ptr<Variable>
VariableController::VariableControllerPrivate::findVariable(QUuid vIdentifier)
{
    std::shared_ptr<Variable> var;
    auto findReply = [vIdentifier](const auto &entry) { return vIdentifier == entry.second; };

    auto end = m_VariableToIdentifierMap.cend();
    auto it = std::find_if(m_VariableToIdentifierMap.cbegin(), end, findReply);
    if (it != end) {
        var = it->first;
    }
    else {
        qCCritical(LOG_VariableController())
            << tr("Impossible to find the variable with the identifier: ") << vIdentifier;
    }

    return var;
}

std::shared_ptr<IDataSeries> VariableController::VariableControllerPrivate::retrieveDataSeries(
    const QVector<AcquisitionDataPacket> acqDataPacketVector)
{
    qCDebug(LOG_VariableController()) << tr("TORM: retrieveDataSeries acqDataPacketVector size")
                                      << acqDataPacketVector.size();
    std::shared_ptr<IDataSeries> dataSeries;
    if (!acqDataPacketVector.isEmpty()) {
        dataSeries = acqDataPacketVector[0].m_DateSeries;
        for (int i = 1; i < acqDataPacketVector.size(); ++i) {
            dataSeries->merge(acqDataPacketVector[i].m_DateSeries.get());
        }
    }
    qCDebug(LOG_VariableController()) << tr("TORM: retrieveDataSeries acqDataPacketVector size END")
                                      << acqDataPacketVector.size();
    return dataSeries;
}

void VariableController::VariableControllerPrivate::registerProvider(
    std::shared_ptr<IDataProvider> provider)
{
    if (m_ProviderSet.find(provider) == m_ProviderSet.end()) {
        qCDebug(LOG_VariableController()) << tr("Registering of a new provider")
                                          << provider->objectName();
        m_ProviderSet.insert(provider);
        connect(provider.get(), &IDataProvider::dataProvided, m_VariableAcquisitionWorker.get(),
                &VariableAcquisitionWorker::onVariableDataAcquired);
        connect(provider.get(), &IDataProvider::dataProvidedProgress,
                m_VariableAcquisitionWorker.get(),
                &VariableAcquisitionWorker::onVariableRetrieveDataInProgress);
        connect(provider.get(), &IDataProvider::dataProvidedFailed,
                m_VariableAcquisitionWorker.get(),
                &VariableAcquisitionWorker::onVariableAcquisitionFailed);
    }
    else {
        qCDebug(LOG_VariableController()) << tr("Cannot register provider, it already exists ");
    }
}

QUuid VariableController::VariableControllerPrivate::acceptVariableRequest(
    QUuid varId, std::shared_ptr<IDataSeries> dataSeries)
{
    auto itVarHandler = m_VarIdToVarRequestHandler.find(varId);
    if (itVarHandler == m_VarIdToVarRequestHandler.cend()) {
        return QUuid();
    }

    auto varHandler = itVarHandler->second.get();
    if (varHandler->m_State == VariableRequestHandlerState::OFF) {
        qCCritical(LOG_VariableController())
            << tr("acceptVariableRequest impossible on a variable with OFF state");
    }

    varHandler->m_RunningVarRequest.m_DataSeries = dataSeries;
    varHandler->m_CanUpdate = true;

    // Element traité, on a déjà toutes les données necessaires
    auto varGroupId = varHandler->m_RunningVarRequest.m_VariableGroupId;
    qCDebug(LOG_VariableController()) << "Variable::acceptVariableRequest" << varGroupId
                                      << m_VarGroupIdToVarIds.size();

    return varHandler->m_RunningVarRequest.m_VariableGroupId;
}

void VariableController::VariableControllerPrivate::updateVariables(QUuid varRequestId)
{
    qCDebug(LOG_VariableController()) << "VariableControllerPrivate::updateVariables"
                                      << QThread::currentThread()->objectName() << varRequestId;

    auto varGroupIdToVarIdsIt = m_VarGroupIdToVarIds.find(varRequestId);
    if (varGroupIdToVarIdsIt == m_VarGroupIdToVarIds.end()) {
        qCWarning(LOG_VariableController())
            << tr("Impossible to updateVariables of unknown variables") << varRequestId;
        return;
    }

    auto &varIds = varGroupIdToVarIdsIt->second;
    auto varIdsEnd = varIds.end();
    bool processVariableUpdate = true;
    qCDebug(LOG_VariableController()) << "VariableControllerPrivate::updateVariables"
                                      << varRequestId << varIds.size();
    for (auto varIdsIt = varIds.begin(); (varIdsIt != varIdsEnd) && processVariableUpdate;
         ++varIdsIt) {
        auto itVarHandler = m_VarIdToVarRequestHandler.find(*varIdsIt);
        if (itVarHandler != m_VarIdToVarRequestHandler.cend()) {
            processVariableUpdate &= itVarHandler->second->m_CanUpdate;
        }
    }

    if (processVariableUpdate) {
        qCDebug(LOG_VariableController()) << "Final update OK for the var request" << varIds.size();
        for (auto varIdsIt = varIds.begin(); varIdsIt != varIdsEnd; ++varIdsIt) {
            auto itVarHandler = m_VarIdToVarRequestHandler.find(*varIdsIt);
            if (itVarHandler != m_VarIdToVarRequestHandler.cend()) {
                if (auto var = findVariable(*varIdsIt)) {
                    auto &varRequest = itVarHandler->second->m_RunningVarRequest;
                    var->setRange(varRequest.m_RangeRequested);
                    var->setCacheRange(varRequest.m_CacheRangeRequested);
                    qCDebug(LOG_VariableController()) << tr("1: onDataProvided")
                                                      << varRequest.m_RangeRequested
                                                      << varRequest.m_CacheRangeRequested;
                    qCDebug(LOG_VariableController()) << tr("2: onDataProvided var points before")
                                                      << var->nbPoints()
                                                      << varRequest.m_DataSeries->nbPoints();
                    var->mergeDataSeries(varRequest.m_DataSeries);
                    qCDebug(LOG_VariableController()) << tr("3: onDataProvided var points after")
                                                      << var->nbPoints();

                    emit var->updated();
                    qCDebug(LOG_VariableController()) << tr("Update OK");
                }
                else {
                    qCCritical(LOG_VariableController())
                        << tr("Impossible to update data to a null variable");
                }
            }
        }
        updateVariableRequest(varRequestId);

        // cleaning varRequestId
        qCDebug(LOG_VariableController()) << tr("m_VarGroupIdToVarIds erase") << varRequestId;
        m_VarGroupIdToVarIds.erase(varRequestId);
        if (m_VarGroupIdToVarIds.empty()) {
            emit q->acquisitionFinished();
        }
    }
}


void VariableController::VariableControllerPrivate::updateVariableRequest(QUuid varRequestId)
{
    auto varGroupIdToVarIdsIt = m_VarGroupIdToVarIds.find(varRequestId);
    if (varGroupIdToVarIdsIt == m_VarGroupIdToVarIds.end()) {
        qCCritical(LOG_VariableController()) << QObject::tr(
            "Impossible to updateVariableRequest since varGroupdId isn't here anymore");

        return;
    }

    auto &varIds = varGroupIdToVarIdsIt->second;
    auto varIdsEnd = varIds.end();
    for (auto varIdsIt = varIds.begin(); (varIdsIt != varIdsEnd); ++varIdsIt) {
        auto itVarHandler = m_VarIdToVarRequestHandler.find(*varIdsIt);
        if (itVarHandler != m_VarIdToVarRequestHandler.cend()) {

            auto varHandler = itVarHandler->second.get();
            varHandler->m_CanUpdate = false;


            switch (varHandler->m_State) {
                case VariableRequestHandlerState::OFF: {
                    qCCritical(LOG_VariableController())
                        << QObject::tr("Impossible to update a variable with handler in OFF state");
                } break;
                case VariableRequestHandlerState::RUNNING: {
                    varHandler->m_State = VariableRequestHandlerState::OFF;
                    varHandler->m_RunningVarRequest = VariableRequest{};
                    break;
                }
                case VariableRequestHandlerState::PENDING: {
                    varHandler->m_State = VariableRequestHandlerState::RUNNING;
                    varHandler->m_RunningVarRequest = varHandler->m_PendingVarRequest;
                    varHandler->m_PendingVarRequest = VariableRequest{};
                    auto var = findVariable(itVarHandler->first);
                    executeVarRequest(var, varHandler->m_RunningVarRequest);
                    updateVariables(varHandler->m_RunningVarRequest.m_VariableGroupId);
                    break;
                }
                default:
                    qCCritical(LOG_VariableController())
                        << QObject::tr("Unknown VariableRequestHandlerState");
            }
        }
    }
}


void VariableController::VariableControllerPrivate::cancelVariableRequest(QUuid varRequestId)
{
    qCDebug(LOG_VariableController()) << tr("cancelVariableRequest") << varRequestId;

    auto varGroupIdToVarIdsIt = m_VarGroupIdToVarIds.find(varRequestId);
    if (varGroupIdToVarIdsIt == m_VarGroupIdToVarIds.end()) {
        qCCritical(LOG_VariableController())
            << tr("Impossible to cancelVariableRequest for unknown varGroupdId") << varRequestId;
        return;
    }

    auto &varIds = varGroupIdToVarIdsIt->second;
    auto varIdsEnd = varIds.end();
    for (auto varIdsIt = varIds.begin(); (varIdsIt != varIdsEnd); ++varIdsIt) {
        auto itVarHandler = m_VarIdToVarRequestHandler.find(*varIdsIt);
        if (itVarHandler != m_VarIdToVarRequestHandler.cend()) {

            auto varHandler = itVarHandler->second.get();
            varHandler->m_VarId = QUuid{};
            switch (varHandler->m_State) {
                case VariableRequestHandlerState::OFF: {
                    qCWarning(LOG_VariableController())
                        << QObject::tr("Impossible to cancel a variable with no running request");
                    break;
                }
                case VariableRequestHandlerState::RUNNING: {

                    if (varHandler->m_RunningVarRequest.m_VariableGroupId == varRequestId) {
                        auto var = findVariable(itVarHandler->first);
                        auto varProvider = m_VariableToProviderMap.at(var);
                        if (varProvider != nullptr) {
                            m_VariableAcquisitionWorker->abortProgressRequested(
                                itVarHandler->first);
                        }
                        m_VariableModel->setDataProgress(var, 0.0);
                        varHandler->m_CanUpdate = false;
                        varHandler->m_State = VariableRequestHandlerState::OFF;
                        varHandler->m_RunningVarRequest = VariableRequest{};
                    }
                    else {
                        // TODO: log Impossible to cancel the running variable request beacause its
                        // varRequestId isn't not the canceled one
                    }
                    break;
                }
                case VariableRequestHandlerState::PENDING: {
                    if (varHandler->m_RunningVarRequest.m_VariableGroupId == varRequestId) {
                        auto var = findVariable(itVarHandler->first);
                        auto varProvider = m_VariableToProviderMap.at(var);
                        if (varProvider != nullptr) {
                            m_VariableAcquisitionWorker->abortProgressRequested(
                                itVarHandler->first);
                        }
                        m_VariableModel->setDataProgress(var, 0.0);
                        varHandler->m_CanUpdate = false;
                        varHandler->m_State = VariableRequestHandlerState::RUNNING;
                        varHandler->m_RunningVarRequest = varHandler->m_PendingVarRequest;
                        varHandler->m_PendingVarRequest = VariableRequest{};
                        executeVarRequest(var, varHandler->m_RunningVarRequest);
                    }
                    else if (varHandler->m_PendingVarRequest.m_VariableGroupId == varRequestId) {
                        varHandler->m_State = VariableRequestHandlerState::RUNNING;
                        varHandler->m_PendingVarRequest = VariableRequest{};
                    }
                    else {
                        // TODO: log Impossible to cancel the variable request beacause its
                        // varRequestId isn't not the canceled one
                    }
                    break;
                }
                default:
                    qCCritical(LOG_VariableController())
                        << QObject::tr("Unknown VariableRequestHandlerState");
            }
        }
    }
    qCDebug(LOG_VariableController()) << tr("cancelVariableRequest: erase") << varRequestId;
    m_VarGroupIdToVarIds.erase(varRequestId);
    if (m_VarGroupIdToVarIds.empty()) {
        emit q->acquisitionFinished();
    }
}

void VariableController::VariableControllerPrivate::executeVarRequest(std::shared_ptr<Variable> var,
                                                                      VariableRequest &varRequest)
{
    qCDebug(LOG_VariableController()) << tr("TORM: executeVarRequest");

    auto varIdIt = m_VariableToIdentifierMap.find(var);
    if (varIdIt == m_VariableToIdentifierMap.cend()) {
        qCWarning(LOG_VariableController()) << tr(
            "Can't execute request of a variable that is not registered (may has been deleted)");
        return;
    }

    auto varId = varIdIt->second;

    auto varCacheRange = var->cacheRange();
    auto varCacheRangeRequested = varRequest.m_CacheRangeRequested;
    auto notInCacheRangeList
        = Variable::provideNotInCacheRangeList(varCacheRange, varCacheRangeRequested);
    auto inCacheRangeList
        = Variable::provideInCacheRangeList(varCacheRange, varCacheRangeRequested);

    if (!notInCacheRangeList.empty()) {

        auto varProvider = m_VariableToProviderMap.at(var);
        if (varProvider != nullptr) {
            qCDebug(LOG_VariableController()) << "executeVarRequest " << varRequest.m_RangeRequested
                                              << varRequest.m_CacheRangeRequested;
            m_VariableAcquisitionWorker->pushVariableRequest(
                varRequest.m_VariableGroupId, varId, varRequest.m_RangeRequested,
                varRequest.m_CacheRangeRequested,
                DataProviderParameters{std::move(notInCacheRangeList), var->metadata()},
                varProvider);
        }
        else {
            qCCritical(LOG_VariableController())
                << "Impossible to provide data with a null provider";
        }

        if (!inCacheRangeList.empty()) {
            emit q->updateVarDisplaying(var, inCacheRangeList.first());
        }
    }
    else {
        acceptVariableRequest(varId,
                              var->dataSeries()->subDataSeries(varRequest.m_CacheRangeRequested));
    }
}

bool VariableController::VariableControllerPrivate::hasPendingDownloads()
{
    return !m_VarGroupIdToVarIds.empty();
}

template <typename VariableIterator>
void VariableController::VariableControllerPrivate::desynchronize(VariableIterator variableIt,
                                                                  const QUuid &syncGroupId)
{
    const auto &variable = variableIt->first;
    const auto &variableId = variableIt->second;

    // Gets synchronization group
    auto groupIt = m_GroupIdToVariableSynchronizationGroupMap.find(syncGroupId);
    if (groupIt == m_GroupIdToVariableSynchronizationGroupMap.cend()) {
        qCCritical(LOG_VariableController())
            << tr("Can't desynchronize variable %1: unknown synchronization group")
                   .arg(variable->name());
        return;
    }

    // Removes variable from synchronization group
    auto synchronizationGroup = groupIt->second;
    synchronizationGroup->removeVariable(variableId);

    // Removes link between variable and synchronization group
    m_VariableIdGroupIdMap.erase(variableId);
}
