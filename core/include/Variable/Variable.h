#ifndef SCIQLOP_VARIABLE_H
#define SCIQLOP_VARIABLE_H

#include <Data/SqpDateTime.h>


#include <QLoggingCategory>
#include <QObject>

#include <Common/spimpl.h>

Q_DECLARE_LOGGING_CATEGORY(LOG_Variable)

class IDataSeries;
class QString;

/**
 * @brief The Variable class represents a variable in SciQlop.
 */
class Variable : public QObject {

    Q_OBJECT

public:
    explicit Variable(const QString &name, const QString &unit, const QString &mission,
                      const SqpDateTime &dateTime);

    QString name() const noexcept;
    QString mission() const noexcept;
    QString unit() const noexcept;
    SqpDateTime dateTime() const noexcept;
    void setDateTime(const SqpDateTime &dateTime) noexcept;

    /// @return the data of the variable, nullptr if there is no data
    IDataSeries *dataSeries() const noexcept;

    bool contains(const SqpDateTime &dateTime);
    bool intersect(const SqpDateTime &dateTime);
    void setDataSeries(std::unique_ptr<IDataSeries> dataSeries) noexcept;

public slots:
    void onAddDataSeries(std::shared_ptr<IDataSeries> dataSeries) noexcept;

signals:
    void dataCacheUpdated();


private:
    class VariablePrivate;
    spimpl::unique_impl_ptr<VariablePrivate> impl;
};

// Required for using shared_ptr in signals/slots
Q_DECLARE_METATYPE(std::shared_ptr<Variable>)

#endif // SCIQLOP_VARIABLE_H
