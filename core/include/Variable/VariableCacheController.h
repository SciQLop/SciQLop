#ifndef SCIQLOP_VARIABLECACHECONTROLLER_H
#define SCIQLOP_VARIABLECACHECONTROLLER_H

#include <QObject>

#include <Data/SqpDateTime.h>

#include <Common/spimpl.h>

class Variable;

/// This class aims to store in the cache all of the dateTime already requested to the variable.
class VariableCacheController : public QObject {
    Q_OBJECT
public:
    explicit VariableCacheController(QObject *parent = 0);


    void addDateTime(std::shared_ptr<Variable> variable, const SqpDateTime &dateTime);

    /// Return all of the SqpDataTime part of the dateTime whose are not in the cache
    QVector<SqpDateTime> provideNotInCacheDateTimeList(std::shared_ptr<Variable> variable,
                                                       const SqpDateTime &dateTime);


    QVector<SqpDateTime> dateCacheList(std::shared_ptr<Variable> variable) const noexcept;

private:
    class VariableCacheControllerPrivate;
    spimpl::unique_impl_ptr<VariableCacheControllerPrivate> impl;
};

#endif // SCIQLOP_VARIABLECACHECONTROLLER_H
