#include "Variable/VariableAcquisitionWorker.h"

#include "Variable/Variable.h"
#include <unordered_map>

#include <QThread>
Q_LOGGING_CATEGORY(LOG_VariableAcquisitionWorker, "VariableAcquisitionWorker")

struct VariableAcquisitionWorker::VariableAcquisitionWorkerPrivate {

    std::unordered_map<std::shared_ptr<Variable>, QVector<SqpDateTime> >
        m_VariableToSqpDateTimeListMap;
};


VariableAcquisitionWorker::VariableAcquisitionWorker(QObject *parent)
        : QObject{parent}, impl{spimpl::make_unique_impl<VariableAcquisitionWorkerPrivate>()}
{
}

void VariableAcquisitionWorker::pushVariableRequest(QUuid vIdentifier, SqpRange rangeRequest,
                                                    SqpRange cacheRangeRequested,
                                                    DataProviderParameters parameters,
                                                    IDataProvider *provider)
{
}
