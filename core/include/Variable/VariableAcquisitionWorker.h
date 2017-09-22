#ifndef SCIQLOP_VARIABLEACQUISITIONWORKER_H
#define SCIQLOP_VARIABLEACQUISITIONWORKER_H

#include "CoreGlobal.h"

#include <Data/DataProviderParameters.h>
#include <QLoggingCategory>
#include <QObject>
#include <QUuid>

#include <Data/AcquisitionDataPacket.h>
#include <Data/IDataSeries.h>
#include <Data/SqpRange.h>

#include <QLoggingCategory>

#include <Common/spimpl.h>

Q_DECLARE_LOGGING_CATEGORY(LOG_VariableAcquisitionWorker)

class Variable;
class IDataProvider;

/// This class aims to handle all acquisition request
class SCIQLOP_CORE_EXPORT VariableAcquisitionWorker : public QObject {
    Q_OBJECT
public:
    explicit VariableAcquisitionWorker(QObject *parent = 0);
    virtual ~VariableAcquisitionWorker();

    QUuid pushVariableRequest(QUuid varRequestId, QUuid vIdentifier, SqpRange rangeRequested,
                              SqpRange cacheRangeRequested, DataProviderParameters parameters,
                              std::shared_ptr<IDataProvider> provider);

    void abortProgressRequested(QUuid vIdentifier);

    void initialize();
    void finalize();
signals:
    void dataProvided(QUuid vIdentifier, const SqpRange &rangeRequested,
                      const SqpRange &cacheRangeRequested,
                      QVector<AcquisitionDataPacket> dataAcquired);

    void variableRequestInProgress(QUuid vIdentifier, double progress);


    void variableCanceledRequested(QUuid vIdentifier);


public slots:
    void onVariableDataAcquired(QUuid acqIdentifier, std::shared_ptr<IDataSeries> dataSeries,
                                SqpRange dataRangeAcquired);
    void onVariableRetrieveDataInProgress(QUuid acqIdentifier, double progress);
    void onVariableAcquisitionFailed(QUuid acqIdentifier);

private:
    void waitForFinish();

    class VariableAcquisitionWorkerPrivate;
    spimpl::unique_impl_ptr<VariableAcquisitionWorkerPrivate> impl;

private slots:
    void onExecuteRequest(QUuid acqIdentifier);
};

#endif // SCIQLOP_VARIABLEACQUISITIONWORKER_H
