#ifndef SCIQLOP_VARIABLEACQUISITIONWORKER_H
#define SCIQLOP_VARIABLEACQUISITIONWORKER_H

#include "CoreGlobal.h"

#include <Data/DataProviderParameters.h>
#include <QLoggingCategory>
#include <QObject>
#include <QUuid>

#include <Data/SqpDateTime.h>

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

    void pushVariableRequest(QUuid vIdentifier, SqpRange rangeRequest, SqpRange cacheRangeRequested,
                             DataProviderParameters parameters, IDataProvider *provider);

private:
    class VariableAcquisitionWorkerPrivate;
    spimpl::unique_impl_ptr<VariableAcquisitionWorkerPrivate> impl;
};

#endif // SCIQLOP_VARIABLEACQUISITIONWORKER_H
