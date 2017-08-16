#include "Variable/VariableAcquisitionWorker.h"

#include "Variable/Variable.h"

#include <Data/AcquisitionRequest.h>
#include <Data/SqpRange.h>

#include <unordered_map>
#include <utility>

#include <QMutex>
#include <QReadWriteLock>
#include <QThread>

Q_LOGGING_CATEGORY(LOG_VariableAcquisitionWorker, "VariableAcquisitionWorker")

struct VariableAcquisitionWorker::VariableAcquisitionWorkerPrivate {

    explicit VariableAcquisitionWorkerPrivate() : m_Lock{QReadWriteLock::Recursive} {}

    void lockRead() { m_Lock.lockForRead(); }
    void lockWrite() { m_Lock.lockForWrite(); }
    void unlock() { m_Lock.unlock(); }

    void removeVariableRequest(QUuid vIdentifier);

    QMutex m_WorkingMutex;
    QReadWriteLock m_Lock;

    std::map<QUuid, QVector<AcquisitionDataPacket> > m_AcqIdentifierToAcqDataPacketVectorMap;
    std::map<QUuid, AcquisitionRequest> m_AcqIdentifierToAcqRequestMap;
    std::map<QUuid, std::pair<QUuid, QUuid> > m_VIdentifierToCurrrentAcqIdNextIdPairMap;
};


VariableAcquisitionWorker::VariableAcquisitionWorker(QObject *parent)
        : QObject{parent}, impl{spimpl::make_unique_impl<VariableAcquisitionWorkerPrivate>()}
{
}

VariableAcquisitionWorker::~VariableAcquisitionWorker()
{
    qCInfo(LOG_VariableAcquisitionWorker()) << tr("VariableAcquisitionWorker destruction")
                                            << QThread::currentThread();
    this->waitForFinish();
}


void VariableAcquisitionWorker::pushVariableRequest(QUuid vIdentifier, SqpRange rangeRequested,
                                                    SqpRange cacheRangeRequested,
                                                    DataProviderParameters parameters,
                                                    std::shared_ptr<IDataProvider> provider)
{
    qCInfo(LOG_VariableAcquisitionWorker())
        << tr("TORM VariableAcquisitionWorker::pushVariableRequest ") << cacheRangeRequested;

    // Request creation
    auto acqRequest = AcquisitionRequest{};
    acqRequest.m_vIdentifier = vIdentifier;
    acqRequest.m_DataProviderParameters = parameters;
    acqRequest.m_RangeRequested = rangeRequested;
    acqRequest.m_CacheRangeRequested = cacheRangeRequested;
    acqRequest.m_Size = parameters.m_Times.size();
    acqRequest.m_Provider = provider;

    // Register request
    impl->lockWrite();
    impl->m_AcqIdentifierToAcqRequestMap.insert(
        std::make_pair(acqRequest.m_AcqIdentifier, acqRequest));

    auto it = impl->m_VIdentifierToCurrrentAcqIdNextIdPairMap.find(vIdentifier);
    if (it != impl->m_VIdentifierToCurrrentAcqIdNextIdPairMap.cend()) {
        // A current request already exists, we can replace the next one
        it->second.second = acqRequest.m_AcqIdentifier;
        impl->unlock();
    }
    else {
        // First request for the variable, it must be stored and executed
        impl->m_VIdentifierToCurrrentAcqIdNextIdPairMap.insert(
            std::make_pair(vIdentifier, std::make_pair(acqRequest.m_AcqIdentifier, QUuid())));
        impl->unlock();

        QMetaObject::invokeMethod(this, "onExecuteRequest", Qt::QueuedConnection,
                                  Q_ARG(QUuid, acqRequest.m_AcqIdentifier));
    }
}

void VariableAcquisitionWorker::abortProgressRequested(QUuid vIdentifier)
{
    // TODO
}

void VariableAcquisitionWorker::onVariableRetrieveDataInProgress(QUuid acqIdentifier,
                                                                 double progress)
{
    // TODO
}

void VariableAcquisitionWorker::onVariableDataAcquired(QUuid acqIdentifier,
                                                       std::shared_ptr<IDataSeries> dataSeries,
                                                       SqpRange dataRangeAcquired)
{
    qCDebug(LOG_VariableAcquisitionWorker()) << tr("onVariableDataAcquired on range ")
                                             << acqIdentifier << dataRangeAcquired;
    impl->lockWrite();
    auto aIdToARit = impl->m_AcqIdentifierToAcqRequestMap.find(acqIdentifier);
    if (aIdToARit != impl->m_AcqIdentifierToAcqRequestMap.cend()) {
        // Store the result
        auto dataPacket = AcquisitionDataPacket{};
        dataPacket.m_Range = dataRangeAcquired;
        dataPacket.m_DateSeries = dataSeries;

        auto aIdToADPVit = impl->m_AcqIdentifierToAcqDataPacketVectorMap.find(acqIdentifier);
        if (aIdToADPVit != impl->m_AcqIdentifierToAcqDataPacketVectorMap.cend()) {
            // A current request result already exists, we can update it
            aIdToADPVit->second.push_back(dataPacket);
        }
        else {
            // First request result for the variable, it must be stored
            impl->m_AcqIdentifierToAcqDataPacketVectorMap.insert(
                std::make_pair(acqIdentifier, QVector<AcquisitionDataPacket>() << dataPacket));
        }


        // Decrement the counter of the request
        auto &acqRequest = aIdToARit->second;
        acqRequest.m_Size = acqRequest.m_Size - 1;

        // if the counter is 0, we can return data then run the next request if it exists and
        // removed the finished request
        if (acqRequest.m_Size == 0) {
            // Return the data
            aIdToADPVit = impl->m_AcqIdentifierToAcqDataPacketVectorMap.find(acqIdentifier);
            if (aIdToADPVit != impl->m_AcqIdentifierToAcqDataPacketVectorMap.cend()) {
                emit dataProvided(acqRequest.m_vIdentifier, acqRequest.m_RangeRequested,
                                  acqRequest.m_CacheRangeRequested, aIdToADPVit->second);
            }

            // Execute the next one
            auto it
                = impl->m_VIdentifierToCurrrentAcqIdNextIdPairMap.find(acqRequest.m_vIdentifier);

            if (it != impl->m_VIdentifierToCurrrentAcqIdNextIdPairMap.cend()) {
                if (it->second.second.isNull()) {
                    // There is no next request, we can remove the varibale request
                    impl->removeVariableRequest(acqRequest.m_vIdentifier);
                }
                else {
                    auto acqIdentifierToRemove = it->second.first;
                    // Move the next request to the current request
                    it->second.first = it->second.second;
                    it->second.second = QUuid();
                    // Remove AcquisitionRequest and results;
                    impl->m_AcqIdentifierToAcqRequestMap.erase(acqIdentifierToRemove);
                    impl->m_AcqIdentifierToAcqDataPacketVectorMap.erase(acqIdentifierToRemove);
                    // Execute the current request
                    QMetaObject::invokeMethod(this, "onExecuteRequest", Qt::QueuedConnection,
                                              Q_ARG(QUuid, it->second.first));
                }
            }
            else {
                qCCritical(LOG_VariableAcquisitionWorker())
                    << tr("Impossible to execute the acquisition on an unfound variable ");
            }
        }
    }
    else {
        qCCritical(LOG_VariableAcquisitionWorker())
            << tr("Impossible to retrieve AcquisitionRequest for the incoming data");
    }
    impl->unlock();
}

void VariableAcquisitionWorker::onExecuteRequest(QUuid acqIdentifier)
{
    qCInfo(LOG_VariableAcquisitionWorker()) << tr("onExecuteRequest") << QThread::currentThread();
    impl->lockRead();
    auto it = impl->m_AcqIdentifierToAcqRequestMap.find(acqIdentifier);
    if (it != impl->m_AcqIdentifierToAcqRequestMap.cend()) {
        auto request = it->second;
        impl->unlock();
        request.m_Provider->requestDataLoading(acqIdentifier, request.m_DataProviderParameters);
    }
    else {
        impl->unlock();
        // TODO log no acqIdentifier recognized
    }
}

void VariableAcquisitionWorker::initialize()
{
    qCDebug(LOG_VariableAcquisitionWorker()) << tr("VariableAcquisitionWorker init")
                                             << QThread::currentThread();
    impl->m_WorkingMutex.lock();
    qCDebug(LOG_VariableAcquisitionWorker()) << tr("VariableAcquisitionWorker init END");
}

void VariableAcquisitionWorker::finalize()
{
    impl->m_WorkingMutex.unlock();
}

void VariableAcquisitionWorker::waitForFinish()
{
    QMutexLocker locker{&impl->m_WorkingMutex};
}

void VariableAcquisitionWorker::VariableAcquisitionWorkerPrivate::removeVariableRequest(
    QUuid vIdentifier)
{
    lockWrite();
    auto it = m_VIdentifierToCurrrentAcqIdNextIdPairMap.find(vIdentifier);

    if (it != m_VIdentifierToCurrrentAcqIdNextIdPairMap.cend()) {
        // A current request already exists, we can replace the next one

        m_AcqIdentifierToAcqRequestMap.erase(it->second.first);
        m_AcqIdentifierToAcqDataPacketVectorMap.erase(it->second.first);

        m_AcqIdentifierToAcqRequestMap.erase(it->second.second);
        m_AcqIdentifierToAcqDataPacketVectorMap.erase(it->second.second);
    }
    m_VIdentifierToCurrrentAcqIdNextIdPairMap.erase(vIdentifier);
    unlock();
}
