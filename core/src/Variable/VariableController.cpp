#include <Variable/Variable.h>
#include <Variable/VariableAcquisitionWorker.h>
#include <Variable/VariableCacheController.h>
#include <Variable/VariableCacheStrategy.h>
#include <Variable/VariableController.h>
#include <Variable/VariableModel.h>
#include <Variable/VariableSynchronizationGroup.h>

#include <Data/DataProviderParameters.h>
#include <Data/IDataProvider.h>
#include <Data/IDataSeries.h>
#include <Time/TimeController.h>

#include <QMutex>
#include <QThread>
#include <QUuid>
#include <QtCore/QItemSelectionModel>

#include <set>
#include <unordered_map>

Q_LOGGING_CATEGORY(LOG_VariableController, "VariableController")

namespace {

SqpRange computeSynchroRangeRequested(const SqpRange &varRange, const SqpRange &grapheRange,
                                      const SqpRange &oldGraphRange)
{
    auto zoomType = VariableController::getZoomType(grapheRange, oldGraphRange);

    auto varRangeRequested = varRange;
    switch (zoomType) {
        case AcquisitionZoomType::ZoomIn: {
            auto deltaLeft = grapheRange.m_TStart - oldGraphRange.m_TStart;
            auto deltaRight = oldGraphRange.m_TEnd - grapheRange.m_TEnd;
            varRangeRequested.m_TStart += deltaLeft;
            varRangeRequested.m_TEnd -= deltaRight;
            break;
        }

        case AcquisitionZoomType::ZoomOut: {
            auto deltaLeft = oldGraphRange.m_TStart - grapheRange.m_TStart;
            auto deltaRight = grapheRange.m_TEnd - oldGraphRange.m_TEnd;
            varRangeRequested.m_TStart -= deltaLeft;
            varRangeRequested.m_TEnd += deltaRight;
            break;
        }
        case AcquisitionZoomType::PanRight: {
            auto deltaRight = grapheRange.m_TEnd - oldGraphRange.m_TEnd;
            varRangeRequested.m_TStart += deltaRight;
            varRangeRequested.m_TEnd += deltaRight;
            break;
        }
        case AcquisitionZoomType::PanLeft: {
            auto deltaLeft = oldGraphRange.m_TStart - grapheRange.m_TStart;
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
              m_VariableCacheController{std::make_unique<VariableCacheController>()},
              m_VariableCacheStrategy{std::make_unique<VariableCacheStrategy>()},
              m_VariableAcquisitionWorker{std::make_unique<VariableAcquisitionWorker>()}
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


    void processRequest(std::shared_ptr<Variable> var, const SqpRange &rangeRequested);

    QVector<SqpRange> provideNotInCacheDateTimeList(std::shared_ptr<Variable> variable,
                                                    const SqpRange &dateTime);

    std::shared_ptr<Variable> findVariable(QUuid vIdentifier);
    std::shared_ptr<IDataSeries>
    retrieveDataSeries(const QVector<AcquisitionDataPacket> acqDataPacketVector);

    void registerProvider(std::shared_ptr<IDataProvider> provider);

    QMutex m_WorkingMutex;
    /// Variable model. The VariableController has the ownership
    VariableModel *m_VariableModel;
    QItemSelectionModel *m_VariableSelectionModel;


    TimeController *m_TimeController{nullptr};
    std::unique_ptr<VariableCacheController> m_VariableCacheController;
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

void VariableController::abortProgress(std::shared_ptr<Variable> variable)
{
}

void VariableController::createVariable(const QString &name, const QVariantHash &metadata,
                                        std::shared_ptr<IDataProvider> provider) noexcept
{

    if (!impl->m_TimeController) {
        qCCritical(LOG_VariableController())
            << tr("Impossible to create variable: The time controller is null");
        return;
    }

    auto range = impl->m_TimeController->dateTime();

    if (auto newVariable = impl->m_VariableModel->createVariable(name, range, metadata)) {
        auto identifier = QUuid::createUuid();

        // store the provider
        impl->registerProvider(provider);

        // Associate the provider
        impl->m_VariableToProviderMap[newVariable] = provider;
        impl->m_VariableToIdentifierMap[newVariable] = identifier;


        impl->processRequest(newVariable, range);
    }
}

void VariableController::onDateTimeOnSelection(const SqpRange &dateTime)
{
    // TODO check synchronisation
    qCDebug(LOG_VariableController()) << "VariableController::onDateTimeOnSelection"
                                      << QThread::currentThread()->objectName();
    auto selectedRows = impl->m_VariableSelectionModel->selectedRows();

    for (const auto &selectedRow : qAsConst(selectedRows)) {
        if (auto selectedVariable = impl->m_VariableModel->variable(selectedRow.row())) {
            selectedVariable->setRange(dateTime);
            impl->processRequest(selectedVariable, dateTime);

            // notify that rescale operation has to be done
            emit rangeChanged(selectedVariable, dateTime);
        }
    }
}

void VariableController::onDataProvided(QUuid vIdentifier, const SqpRange &rangeRequested,
                                        const SqpRange &cacheRangeRequested,
                                        QVector<AcquisitionDataPacket> dataAcquired)
{
    qCCritical(LOG_VariableController()) << tr("onDataProvided") << dataAcquired.isEmpty();

    auto var = impl->findVariable(vIdentifier);
    if (var != nullptr) {
        var->setRange(rangeRequested);
        var->setCacheRange(cacheRangeRequested);
        qCCritical(LOG_VariableController()) << tr("1: onDataProvided") << rangeRequested;
        qCCritical(LOG_VariableController()) << tr("2: onDataProvided") << cacheRangeRequested;

        auto retrievedDataSeries = impl->retrieveDataSeries(dataAcquired);
        qCCritical(LOG_VariableController()) << tr("3: onDataProvided")
                                             << retrievedDataSeries->range();
        var->mergeDataSeries(retrievedDataSeries);
        emit var->updated();
    }
    else {
        qCCritical(LOG_VariableController()) << tr("Impossible to provide data to a null variable");
    }
}

void VariableController::onVariableRetrieveDataInProgress(QUuid identifier, double progress)
{
    auto var = impl->findVariable(identifier);
    if (var != nullptr) {
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
    auto vSynchroGroup = std::make_shared<VariableSynchronizationGroup>();
    impl->m_GroupIdToVariableSynchronizationGroupMap.insert(
        std::make_pair(synchronizationGroupId, vSynchroGroup));
}

void VariableController::onRemoveSynchronizationGroupId(QUuid synchronizationGroupId)
{
    impl->m_GroupIdToVariableSynchronizationGroupMap.erase(synchronizationGroupId);
}


void VariableController::onRequestDataLoading(QVector<std::shared_ptr<Variable> > variables,
                                              const SqpRange &range, const SqpRange &oldRange,
                                              bool synchronise)
{
    // NOTE: oldRange isn't really necessary since oldRange == variable->range().

    qCDebug(LOG_VariableController()) << "VariableController::onRequestDataLoading"
                                      << QThread::currentThread()->objectName();
    // we want to load data of the variable for the dateTime.
    // First we check if the cache contains some of them.
    // For the other, we ask the provider to give them.

    foreach (auto var, variables) {
        qCInfo(LOG_VariableController()) << "processRequest for" << var->name();
        impl->processRequest(var, range);
    }

    if (synchronise) {
        // Get the group ids
        qCInfo(LOG_VariableController())
            << "VariableController::onRequestDataLoading for synchro var ENABLE";
        auto groupIds = std::set<QUuid>();
        foreach (auto var, variables) {
            auto vToVIdit = impl->m_VariableToIdentifierMap.find(var);
            if (vToVIdit != impl->m_VariableToIdentifierMap.cend()) {
                auto vId = vToVIdit->second;

                auto vIdToGIdit = impl->m_VariableIdGroupIdMap.find(vId);
                if (vIdToGIdit != impl->m_VariableIdGroupIdMap.cend()) {
                    auto gId = vToVIdit->second;
                    if (groupIds.find(gId) == groupIds.cend()) {
                        groupIds.insert(gId);
                    }
                }
            }
        }

        // We assume here all group ids exist
        foreach (auto gId, groupIds) {
            auto vSynchronizationGroup = impl->m_GroupIdToVariableSynchronizationGroupMap.at(gId);
            auto vSyncIds = vSynchronizationGroup->getIds();
            for (auto vId : vSyncIds) {
                auto var = impl->findVariable(vId);
                if (var != nullptr) {
                    qCInfo(LOG_VariableController()) << "processRequest synchro for" << var->name();
                    auto vSyncRangeRequested
                        = computeSynchroRangeRequested(var->range(), range, oldRange);
                    impl->processRequest(var, vSyncRangeRequested);
                }
                else {
                    qCCritical(LOG_VariableController())
                        << tr("Impossible to synchronize a null variable");
                }
            }
        }
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
                                                                   const SqpRange &rangeRequested)
{

    auto varRangesRequested
        = m_VariableCacheStrategy->computeCacheRange(var->range(), rangeRequested);
    auto notInCacheRangeList = var->provideNotInCacheRangeList(varRangesRequested.second);

    if (!notInCacheRangeList.empty()) {
        // Display part of data which are already there
        // Ask the provider for each data on the dateTimeListNotInCache
        auto identifier = m_VariableToIdentifierMap.at(var);
        auto varProvider = m_VariableToProviderMap.at(var);
        if (varProvider != nullptr) {
            m_VariableAcquisitionWorker->pushVariableRequest(
                identifier, varRangesRequested.first, varRangesRequested.second,
                DataProviderParameters{std::move(notInCacheRangeList), var->metadata()},
                varProvider);
        }
        else {
            qCCritical(LOG_VariableController())
                << "Impossible to provide data with a null provider";
        }
    }
    else {
        var->setRange(rangeRequested);
        var->setCacheRange(varRangesRequested.second);
        var->setDataSeries(var->dataSeries()->subData(varRangesRequested.second));
        emit var->updated();
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
    qCInfo(LOG_VariableController()) << tr("TORM: retrieveDataSeries acqDataPacketVector size")
                                     << acqDataPacketVector.size();
    std::shared_ptr<IDataSeries> dataSeries;
    if (!acqDataPacketVector.isEmpty()) {
        dataSeries = acqDataPacketVector[0].m_DateSeries;
        for (int i = 1; i < acqDataPacketVector.size(); ++i) {
            dataSeries->merge(acqDataPacketVector[i].m_DateSeries.get());
        }
    }

    return dataSeries;
}

void VariableController::VariableControllerPrivate::registerProvider(
    std::shared_ptr<IDataProvider> provider)
{
    if (m_ProviderSet.find(provider) == m_ProviderSet.end()) {
        qCInfo(LOG_VariableController()) << tr("Registering of a new provider")
                                         << provider->objectName();
        m_ProviderSet.insert(provider);
        connect(provider.get(), &IDataProvider::dataProvided, m_VariableAcquisitionWorker.get(),
                &VariableAcquisitionWorker::onVariableDataAcquired);
        connect(provider.get(), &IDataProvider::dataProvidedProgress,
                m_VariableAcquisitionWorker.get(),
                &VariableAcquisitionWorker::onVariableRetrieveDataInProgress);
    }
    else {
        qCInfo(LOG_VariableController()) << tr("Cannot register provider, it already exists ");
    }
}
