#include <memory>
#include <vector>
#include <QHash>
#include <Variable/Variable.h>
#include <Variable/VariableSynchronizationGroup.h>
#include "Data/SqpRange.h"
#include <QMutexLocker>
#include <QUuid>

class VariableController2
{

    QHash<QUuid, std::shared_ptr<Variable>> _variables;
    QMutex _variables_lock;

    std::vector<std::unique_ptr<VariableSynchronizationGroup>> _groups;
    QMutex _variables_groups_lock;
public:

    QUuid addVariable(std::shared_ptr<Variable> variable)
    {
        QMutexLocker lock(&_variables_lock);
        QMutexLocker glock(&_variables_groups_lock);

        QUuid uuid = QUuid::createUuid();
        this->_variables[uuid] = variable;
        this->_groups.push_back(std::make_unique<VariableSynchronizationGroup>(uuid));
        return uuid;
    }
    void changeRange(int variable, DateTimeRange r);
    void asyncChangeRange(int variable, DateTimeRange r);
};
