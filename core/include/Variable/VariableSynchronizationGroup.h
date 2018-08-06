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
    explicit VariableSynchronizationGroup(QObject *parent = Q_NULLPTR);
    explicit VariableSynchronizationGroup(QUuid variable, QObject *parent = Q_NULLPTR);

    void addVariable(QUuid vIdentifier);
    void removeVariable(QUuid vIdentifier);

    const std::set<QUuid> &getIds() const noexcept;

private:
    class VariableSynchronizationGroupPrivate;
    spimpl::unique_impl_ptr<VariableSynchronizationGroupPrivate> impl;
};

#endif // SCIQLOP_VARIABLESYNCHRONIZATIONGROUP_H
