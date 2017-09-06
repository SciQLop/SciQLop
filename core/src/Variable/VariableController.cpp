#include <Variable/Variable.h>
#include <Variable/VariableAcquisitionWorker.h>
#include <Variable/VariableCacheStrategy.h>
#include <Variable/VariableController.h>
#include <Variable/VariableModel.h>
#include <Variable/VariableSynchronizationGroup.h>

#include <Data/DataProviderParameters.h>
#include <Data/IDataProvider.h>
#include <Data/IDataSeries.h>
#include <Data/VariableRequest.h>
#include <Time/TimeController.h>

#include <QMutex>
#include <QThread>
#include <QUuid>
#include <QtCore/QItemSelectionModel>

#include <deque>
#include <set>
#include <unordered_map>

Q_LOGGING_CATEGORY(LOG_VariableController, "VariableController")

namespace {

SqpRange computeSynchroRangeRequested(const SqpRange &varRange, const SqpRange &graphRange,
                                      const SqpRange &oldGraphRange)
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
            auto deltaRight = graphRange.m_TEnd - oldGraphRange.m_TEnd;
            varRangeRequested.m_TStart += deltaRight;
            varRangeRequested.m_TEnd += deltaRight;
            break;
        }
        case AcquisitionZoomType::PanLeft: {
            auto deltaLeft = oldGraphRange.m_TStart - graphRange.m_TStart;
            varRangeRequested.m_TStart -= deltaLeft;
            varRangeRequested.m_TEnd -= deltaLeft;
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

struct VariableController::VariableControllerPrivate {
    explicit VariableControllerPrivate(VariableController *parent)
            : m_WorkingMutex{},
              m_VariableModel{new VariableModel{parent}},
              m_VariableSelectionModel{new QItemSelectionModel{m_VariableModel, parent}},
              m_VariableCacheStrategy{std::make_unique<VariableCacheStrategy>()},
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


    void processRequest(std::shared_ptr<Variable> var, const SqpRange &rangeRequested,
                        QUuid varRequestId);

    QVector<SqpRange> provideNotInCacheDateTimeList(std::shared_ptr<Variable> variable,
                                                    const SqpRange &dateTime);

    std::shared_ptr<Variable> findVariable(QUuid vIdentifier);
    std::shared_ptr<IDataSeries>
    retrieveDataSeries(const QVector<AcquisitionDataPacket> acqDataPacketVector);

    void registerProvider(std::shared_ptr<IDataProvider> provider);

    void storeVariableRequest(QUuid varId, QUuid varRequestId, const VariableRequest &varRequest);
    QUuid acceptVariableRequest(QUuid varId, std::shared_ptr<IDataSeries> dataSeries);
    void updateVariableRequest(QUuid varRequestId);
    void cancelVariableRequest(QUuid varRequestId);

    QMutex m_WorkingMutex;
    /// Variable model. The VariableController has the ownership
    VariableModel *m_VariableModel;
    QItemSelectionModel *m_VariableSelectionModel;


    TimeController *m_TimeController{nullptr};
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

    std::map<QUuid, std::map<QUuid, VariableRequest> > m_VarRequestIdToVarIdVarRequestMap;

    std::map<QUuid, std::deque<QUuid> > m_VarIdToVarRequestIdQueueMap;


    VariableController *q;
};


VariableController::VariableController(QObject *parent)
        : QObject{parent}, impl{spimpl::make_unique_impl<VariableControllerPrivate>(this)}
{
    qCDebug(LOG_VariableController()) << tr("VariableController construction")
                                      << QThread::currentThread();

    connect(impl->m_VariableModel, &VariableModel::abortProgessRequested, this,
            &VariableController::onAbortProgressRequested);

    connect(impl->m_VariableAcquisitionWorker.get(), &VariableAcquisitionWorker::dataProvided, this,
            &VariableController::onDataProvided);
    connect(impl->m_VariableAcquisitionWorker.get(),
            &VariableAcquisitionWorker::variableRequestInProgress, this,
            &VariableController::onVariableRetrieveDataInProgress);

    connect(&impl->m_VariableAcquisitionWorkerThread, &QThread::started,
            impl->m_VariableAcquisitionWorker.get(), &VariableAcquisitionWorker::initialize);
    connect(&impl->m_VariableAcquisitionWorkerThread, &QThread::finished,
            impl->m_VariableAcquisitionWorker.get(), &VariableAcquisitionWorker::finalize);


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

void VariableController::setTimeController(TimeController *timeController) noexcept
{
    impl->m_TimeController = timeController;
}

std::shared_ptr<Variable>
VariableController::cloneVariable(std::shared_ptr<Variable> variable) noexcept
{
    // Clones variable
    auto duplicate = variable->clone();

    return duplicate;
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

    // Deletes identifier
    impl->m_VariableToIdentifierMap.erase(variable);

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

void VariableController::abortProgress(std::shared_ptr<Variable> variable)
{
}

std::shared_ptr<Variable>
VariableController::createVariable(const QString &name, const QVariantHash &metadata,
                                   std::shared_ptr<IDataProvider> provider) noexcept
{
    if (!impl->m_TimeController) {
        qCCritical(LOG_VariableController())
            << tr("Impossible to create variable: The time controller is null");
        return nullptr;
    }

    auto range = impl->m_TimeController->dateTime();

    if (auto newVariable = impl->m_VariableModel->createVariable(name, range, metadata)) {
        auto identifier = QUuid::createUuid();

        // store the provider
        impl->registerProvider(provider);

        // Associate the provider
        impl->m_VariableToProviderMap[newVariable] = provider;
        impl->m_VariableToIdentifierMap[newVariable] = identifier;


        auto varRequestId = QUuid::createUuid();
        qCInfo(LOG_VariableController()) << "processRequest for" << name << varRequestId;
        impl->processRequest(newVariable, range, varRequestId);
        impl->updateVariableRequest(varRequestId);

        return newVariable;
    }
}

void VariableController::onDateTimeOnSelection(const SqpRange &dateTime)
{
    // TODO check synchronisation and Rescale
    qCDebug(LOG_VariableController()) << "VariableController::onDateTimeOnSelection"
                                      << QThread::currentThread()->objectName();
    auto selectedRows = impl->m_VariableSelectionModel->selectedRows();
    auto varRequestId = QUuid::createUuid();

    for (const auto &selectedRow : qAsConst(selectedRows)) {
        if (auto selectedVariable = impl->m_VariableModel->variable(selectedRow.row())) {
            selectedVariable->setRange(dateTime);
            impl->processRequest(selectedVariable, dateTime, varRequestId);

            // notify that rescale operation has to be done
            emit rangeChanged(selectedVariable, dateTime);
        }
    }
    impl->updateVariableRequest(varRequestId);
}

void VariableController::onDataProvided(QUuid vIdentifier, const SqpRange &rangeRequested,
                                        const SqpRange &cacheRangeRequested,
                                        QVector<AcquisitionDataPacket> dataAcquired)
{
    auto retrievedDataSeries = impl->retrieveDataSeries(dataAcquired);
    auto varRequestId = impl->acceptVariableRequest(vIdentifier, retrievedDataSeries);
    if (!varRequestId.isNull()) {
        impl->updateVariableRequest(varRequestId);
    }
}

void VariableController::onVariableRetrieveDataInProgress(QUuid identifier, double progress)
{
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
    qCDebug(LOG_VariableController()) << "TORM: VariableController::onAbortProgressRequested"
                                      << QThread::currentThread()->objectName();

    auto it = impl->m_VariableToIdentifierMap.find(variable);
    if (it != impl->m_VariableToIdentifierMap.cend()) {
        impl->m_VariableToProviderMap.at(variable)->requestDataAborting(it->second);
    }
    else {
        qCWarning(LOG_VariableController())
            << tr("Aborting progression of inexistant variable detected !!!")
            << QThread::currentThread()->objectName();
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
            groupIdToVSGIt->second->addVariableId(varToVarIdIt->second);
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


void VariableController::onRequestDataLoading(QVector<std::shared_ptr<Variable> > variables,
                                              const SqpRange &range, const SqpRange &oldRange,
                                              bool synchronise)
{
    // NOTE: oldRange isn't really necessary since oldRange == variable->range().

    // we want to load data of the variable for the dateTime.
    // First we check if the cache contains some of them.
    // For the other, we ask the provider to give them.

    auto varRequestId = QUuid::createUuid();
    qCInfo(LOG_VariableController()) << "VariableController::onRequestDataLoading"
                                     << QThread::currentThread()->objectName() << varRequestId;

    for (const auto &var : variables) {
        qCDebug(LOG_VariableController()) << "processRequest for" << var->name() << varRequestId;
        impl->processRequest(var, range, varRequestId);
    }

    if (synchronise) {
        // Get the group ids
        qCDebug(LOG_VariableController())
            << "TORM VariableController::onRequestDataLoading for synchro var ENABLE";
        auto groupIds = std::set<QUuid>{};
        auto groupIdToOldRangeMap = std::map<QUuid, SqpRange>{};
        for (const auto &var : variables) {
            auto varToVarIdIt = impl->m_VariableToIdentifierMap.find(var);
            if (varToVarIdIt != impl->m_VariableToIdentifierMap.cend()) {
                auto vId = varToVarIdIt->second;
                auto varIdToGroupIdIt = impl->m_VariableIdGroupIdMap.find(vId);
                if (varIdToGroupIdIt != impl->m_VariableIdGroupIdMap.cend()) {
                    auto gId = varIdToGroupIdIt->second;
                    groupIdToOldRangeMap.insert(std::make_pair(gId, var->range()));
                    if (groupIds.find(gId) == groupIds.cend()) {
                        qCDebug(LOG_VariableController()) << "Synchro detect group " << gId;
                        groupIds.insert(gId);
                    }
                }
            }
        }

        // We assume here all group ids exist
        for (const auto &gId : groupIds) {
            auto vSynchronizationGroup = impl->m_GroupIdToVariableSynchronizationGroupMap.at(gId);
            auto vSyncIds = vSynchronizationGroup->getIds();
            qCDebug(LOG_VariableController()) << "Var in synchro group ";
            for (auto vId : vSyncIds) {
                auto var = impl->findVariable(vId);

                // Don't process already processed var
                if (!variables.contains(var)) {
                    if (var != nullptr) {
                        qCDebug(LOG_VariableController()) << "processRequest synchro for"
                                                          << var->name();
                        auto vSyncRangeRequested = computeSynchroRangeRequested(
                            var->range(), range, groupIdToOldRangeMap.at(gId));
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
    }

    impl->updateVariableRequest(varRequestId);
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

AcquisitionZoomType VariableController::getZoomType(const SqpRange &range, const SqpRange &oldRange)
{
    // t1.m_TStart <= t2.m_TStart && t2.m_TEnd <= t1.m_TEnd
    auto zoomType = AcquisitionZoomType::Unknown;
    if (range.m_TStart <= oldRange.m_TStart && oldRange.m_TEnd <= range.m_TEnd) {
        zoomType = AcquisitionZoomType::ZoomOut;
    }
    else if (range.m_TStart > oldRange.m_TStart && range.m_TEnd > oldRange.m_TEnd) {
        zoomType = AcquisitionZoomType::PanRight;
    }
    else if (range.m_TStart < oldRange.m_TStart && range.m_TEnd < oldRange.m_TEnd) {
        zoomType = AcquisitionZoomType::PanLeft;
    }
    else if (range.m_TStart > oldRange.m_TStart && oldRange.m_TEnd > range.m_TEnd) {
        zoomType = AcquisitionZoomType::ZoomIn;
    }
    else {
        qCCritical(LOG_VariableController()) << "getZoomType: Unknown type detected";
    }
    return zoomType;
}

void VariableController::VariableControllerPrivate::processRequest(std::shared_ptr<Variable> var,
                                                                   const SqpRange &rangeRequested,
                                                                   QUuid varRequestId)
{

    // TODO: protect at
    auto varRequest = VariableRequest{};
    auto varId = m_VariableToIdentifierMap.at(var);

    auto varStrategyRangesRequested
        = m_VariableCacheStrategy->computeStrategyRanges(var->range(), rangeRequested);
    auto notInCacheRangeList = var->provideNotInCacheRangeList(varStrategyRangesRequested.second);
    auto inCacheRangeList = var->provideInCacheRangeList(varStrategyRangesRequested.second);

    if (!notInCacheRangeList.empty()) {
        varRequest.m_RangeRequested = varStrategyRangesRequested.first;
        varRequest.m_CacheRangeRequested = varStrategyRangesRequested.second;
        qCDebug(LOG_VariableAcquisitionWorker()) << tr("TORM processRequest RR ") << rangeRequested;
        qCDebug(LOG_VariableAcquisitionWorker()) << tr("TORM processRequest R  ")
                                                 << varStrategyRangesRequested.first;
        qCDebug(LOG_VariableAcquisitionWorker()) << tr("TORM processRequest CR ")
                                                 << varStrategyRangesRequested.second;
        // store VarRequest
        storeVariableRequest(varId, varRequestId, varRequest);

        auto varProvider = m_VariableToProviderMap.at(var);
        if (varProvider != nullptr) {
            auto varRequestIdCanceled = m_VariableAcquisitionWorker->pushVariableRequest(
                varRequestId, varId, varStrategyRangesRequested.first,
                varStrategyRangesRequested.second,
                DataProviderParameters{std::move(notInCacheRangeList), var->metadata()},
                varProvider);

            if (!varRequestIdCanceled.isNull()) {
                qCInfo(LOG_VariableAcquisitionWorker()) << tr("varRequestIdCanceled: ")
                                                        << varRequestIdCanceled;
                cancelVariableRequest(varRequestIdCanceled);
            }
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

        varRequest.m_RangeRequested = varStrategyRangesRequested.first;
        varRequest.m_CacheRangeRequested = varStrategyRangesRequested.second;
        // store VarRequest
        storeVariableRequest(varId, varRequestId, varRequest);
        acceptVariableRequest(varId,
                              var->dataSeries()->subDataSeries(varStrategyRangesRequested.second));
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
    }
    else {
        qCDebug(LOG_VariableController()) << tr("Cannot register provider, it already exists ");
    }
}

void VariableController::VariableControllerPrivate::storeVariableRequest(
    QUuid varId, QUuid varRequestId, const VariableRequest &varRequest)
{
    // First request for the variable. we can create an entry for it
    auto varIdToVarRequestIdQueueMapIt = m_VarIdToVarRequestIdQueueMap.find(varId);
    if (varIdToVarRequestIdQueueMapIt == m_VarIdToVarRequestIdQueueMap.cend()) {
        auto varRequestIdQueue = std::deque<QUuid>{};
        qCDebug(LOG_VariableController()) << tr("Store REQUEST in  QUEUE");
        varRequestIdQueue.push_back(varRequestId);
        m_VarIdToVarRequestIdQueueMap.insert(std::make_pair(varId, std::move(varRequestIdQueue)));
    }
    else {
        qCDebug(LOG_VariableController()) << tr("Store REQUEST in EXISTING QUEUE");
        auto &varRequestIdQueue = varIdToVarRequestIdQueueMapIt->second;
        varRequestIdQueue.push_back(varRequestId);
    }

    auto varRequestIdToVarIdVarRequestMapIt = m_VarRequestIdToVarIdVarRequestMap.find(varRequestId);
    if (varRequestIdToVarIdVarRequestMapIt == m_VarRequestIdToVarIdVarRequestMap.cend()) {
        auto varIdToVarRequestMap = std::map<QUuid, VariableRequest>{};
        varIdToVarRequestMap.insert(std::make_pair(varId, varRequest));
        qCDebug(LOG_VariableController()) << tr("Store REQUESTID in MAP");
        m_VarRequestIdToVarIdVarRequestMap.insert(
            std::make_pair(varRequestId, std::move(varIdToVarRequestMap)));
    }
    else {
        auto &varIdToVarRequestMap = varRequestIdToVarIdVarRequestMapIt->second;
        qCDebug(LOG_VariableController()) << tr("Store REQUESTID in EXISTING MAP");
        varIdToVarRequestMap.insert(std::make_pair(varId, varRequest));
    }
}

QUuid VariableController::VariableControllerPrivate::acceptVariableRequest(
    QUuid varId, std::shared_ptr<IDataSeries> dataSeries)
{
    QUuid varRequestId;
    auto varIdToVarRequestIdQueueMapIt = m_VarIdToVarRequestIdQueueMap.find(varId);
    if (varIdToVarRequestIdQueueMapIt != m_VarIdToVarRequestIdQueueMap.cend()) {
        auto &varRequestIdQueue = varIdToVarRequestIdQueueMapIt->second;
        varRequestId = varRequestIdQueue.front();
        auto varRequestIdToVarIdVarRequestMapIt
            = m_VarRequestIdToVarIdVarRequestMap.find(varRequestId);
        if (varRequestIdToVarIdVarRequestMapIt != m_VarRequestIdToVarIdVarRequestMap.cend()) {
            auto &varIdToVarRequestMap = varRequestIdToVarIdVarRequestMapIt->second;
            auto varIdToVarRequestMapIt = varIdToVarRequestMap.find(varId);
            if (varIdToVarRequestMapIt != varIdToVarRequestMap.cend()) {
                qCDebug(LOG_VariableController()) << tr("acceptVariableRequest");
                auto &varRequest = varIdToVarRequestMapIt->second;
                varRequest.m_DataSeries = dataSeries;
                varRequest.m_CanUpdate = true;
            }
            else {
                qCDebug(LOG_VariableController())
                    << tr("Impossible to acceptVariableRequest of a unknown variable id attached "
                          "to a variableRequestId")
                    << varRequestId << varId;
            }
        }
        else {
            qCCritical(LOG_VariableController())
                << tr("Impossible to acceptVariableRequest of a unknown variableRequestId")
                << varRequestId;
        }

        qCDebug(LOG_VariableController()) << tr("1: erase REQUEST in  QUEUE ?")
                                          << varRequestIdQueue.size();
        varRequestIdQueue.pop_front();
        qCDebug(LOG_VariableController()) << tr("2: erase REQUEST in  QUEUE ?")
                                          << varRequestIdQueue.size();
        if (varRequestIdQueue.empty()) {
            m_VarIdToVarRequestIdQueueMap.erase(varId);
        }
    }
    else {
        qCCritical(LOG_VariableController())
            << tr("Impossible to acceptVariableRequest of a unknown variable id") << varId;
    }

    return varRequestId;
}

void VariableController::VariableControllerPrivate::updateVariableRequest(QUuid varRequestId)
{

    auto varRequestIdToVarIdVarRequestMapIt = m_VarRequestIdToVarIdVarRequestMap.find(varRequestId);
    if (varRequestIdToVarIdVarRequestMapIt != m_VarRequestIdToVarIdVarRequestMap.cend()) {
        bool processVariableUpdate = true;
        auto &varIdToVarRequestMap = varRequestIdToVarIdVarRequestMapIt->second;
        for (auto varIdToVarRequestMapIt = varIdToVarRequestMap.cbegin();
             (varIdToVarRequestMapIt != varIdToVarRequestMap.cend()) && processVariableUpdate;
             ++varIdToVarRequestMapIt) {
            processVariableUpdate &= varIdToVarRequestMapIt->second.m_CanUpdate;
            qCDebug(LOG_VariableController()) << tr("updateVariableRequest")
                                              << processVariableUpdate;
        }

        if (processVariableUpdate) {
            for (auto varIdToVarRequestMapIt = varIdToVarRequestMap.cbegin();
                 varIdToVarRequestMapIt != varIdToVarRequestMap.cend(); ++varIdToVarRequestMapIt) {
                if (auto var = findVariable(varIdToVarRequestMapIt->first)) {
                    auto &varRequest = varIdToVarRequestMapIt->second;
                    var->setRange(varRequest.m_RangeRequested);
                    var->setCacheRange(varRequest.m_CacheRangeRequested);
                    qCDebug(LOG_VariableController()) << tr("1: onDataProvided")
                                                      << varRequest.m_RangeRequested;
                    qCDebug(LOG_VariableController()) << tr("2: onDataProvided")
                                                      << varRequest.m_CacheRangeRequested;
                    var->mergeDataSeries(varRequest.m_DataSeries);
                    qCDebug(LOG_VariableController()) << tr("3: onDataProvided")
                                                      << varRequest.m_DataSeries->range();
                    qCDebug(LOG_VariableController()) << tr("4: onDataProvided");

                    /// @todo MPL: confirm
                    // Variable update is notified only if there is no pending request for it
                    if (m_VarIdToVarRequestIdQueueMap.count(varIdToVarRequestMapIt->first) == 0) {
                        emit var->updated();
                    }
                }
                else {
                    qCCritical(LOG_VariableController())
                        << tr("Impossible to update data to a null variable");
                }
            }

            // cleaning varRequestId
            qCDebug(LOG_VariableController()) << tr("0: erase REQUEST in  MAP ?")
                                              << m_VarRequestIdToVarIdVarRequestMap.size();
            m_VarRequestIdToVarIdVarRequestMap.erase(varRequestId);
            qCDebug(LOG_VariableController()) << tr("1: erase REQUEST in  MAP ?")
                                              << m_VarRequestIdToVarIdVarRequestMap.size();
        }
    }
    else {
        qCCritical(LOG_VariableController())
            << tr("Cannot updateVariableRequest for a unknow varRequestId") << varRequestId;
    }
}

void VariableController::VariableControllerPrivate::cancelVariableRequest(QUuid varRequestId)
{
    // cleaning varRequestId
    m_VarRequestIdToVarIdVarRequestMap.erase(varRequestId);

    for (auto varIdToVarRequestIdQueueMapIt = m_VarIdToVarRequestIdQueueMap.begin();
         varIdToVarRequestIdQueueMapIt != m_VarIdToVarRequestIdQueueMap.end();) {
        auto &varRequestIdQueue = varIdToVarRequestIdQueueMapIt->second;
        varRequestIdQueue.erase(
            std::remove(varRequestIdQueue.begin(), varRequestIdQueue.end(), varRequestId),
            varRequestIdQueue.end());
        if (varRequestIdQueue.empty()) {
            varIdToVarRequestIdQueueMapIt
                = m_VarIdToVarRequestIdQueueMap.erase(varIdToVarRequestIdQueueMapIt);
        }
        else {
            ++varIdToVarRequestIdQueueMapIt;
        }
    }
}
