#ifndef SCIQLOP_VARIABLE_H
#define SCIQLOP_VARIABLE_H

#include "CoreGlobal.h"

#include <Data/SqpRange.h>

#include <QLoggingCategory>
#include <QObject>

#include <Common/MetaTypes.h>
#include <Common/spimpl.h>

Q_DECLARE_LOGGING_CATEGORY(LOG_Variable)

class IDataSeries;
class QString;

/**
 * @brief The Variable class represents a variable in SciQlop.
 */
class SCIQLOP_CORE_EXPORT Variable : public QObject {

    Q_OBJECT

public:
    explicit Variable(const QString &name, const SqpRange &dateTime,
                      const QVariantHash &metadata = {});

    QString name() const noexcept;
    SqpRange dateTime() const noexcept;
    void setDateTime(const SqpRange &dateTime) noexcept;

    /// @return the data of the variable, nullptr if there is no data
    IDataSeries *dataSeries() const noexcept;

    QVariantHash metadata() const noexcept;

    bool contains(const SqpRange &dateTime) const noexcept;
    bool intersect(const SqpRange &dateTime) const noexcept;
    bool isInside(const SqpRange &dateTime) const noexcept;

public slots:
    void setDataSeries(std::shared_ptr<IDataSeries> dataSeries) noexcept;

signals:
    void updated();

private:
    class VariablePrivate;
    spimpl::unique_impl_ptr<VariablePrivate> impl;
};

// Required for using shared_ptr in signals/slots
SCIQLOP_REGISTER_META_TYPE(VARIABLE_PTR_REGISTRY, std::shared_ptr<Variable>)

#endif // SCIQLOP_VARIABLE_H
