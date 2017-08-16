#ifndef SCIQLOP_VARIABLESYNCHRONIZATIONGROUP_H
#define SCIQLOP_VARIABLESYNCHRONIZATIONGROUP_H

#include "CoreGlobal.h"

#include <QLoggingCategory>
#include <QObject>
#include <QUuid>

#include <Data/SqpRange.h>

#include <set>

#include <QLoggingCategory>

#include <Common/spimpl.h>

Q_DECLARE_LOGGING_CATEGORY(LOG_VariableSynchronizationGroup)

class Variable;

/// This class aims to hande the cache strategy.
class SCIQLOP_CORE_EXPORT VariableSynchronizationGroup : public QObject {
    Q_OBJECT
public:
    explicit VariableSynchronizationGroup(QObject *parent = 0);

    void addVariableId(QUuid vIdentifier);
    void removeVariableId(QUuid vIdentifier);

    const std::set<QUuid> &getIds() const noexcept;

private:
    class VariableSynchronizationGroupPrivate;
    spimpl::unique_impl_ptr<VariableSynchronizationGroupPrivate> impl;
};

#endif // SCIQLOP_VARIABLESYNCHRONIZATIONGROUP_H
