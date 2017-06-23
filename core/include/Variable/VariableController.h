#ifndef SCIQLOP_VARIABLECONTROLLER_H
#define SCIQLOP_VARIABLECONTROLLER_H

#include <Data/SqpDateTime.h>

#include <QLoggingCategory>
#include <QObject>

#include <Common/spimpl.h>


class IDataProvider;
class TimeController;
class Variable;
class VariableModel;

Q_DECLARE_LOGGING_CATEGORY(LOG_VariableController)

/**
 * @brief The VariableController class aims to handle the variables in SciQlop.
 */
class VariableController : public QObject {
    Q_OBJECT
public:
    explicit VariableController(QObject *parent = 0);
    virtual ~VariableController();

    VariableModel *variableModel() noexcept;

    void setTimeController(TimeController *timeController) noexcept;


    /// Request the data loading of the variable whithin dateTime
    void requestDataLoading(std::shared_ptr<Variable> variable, const SqpDateTime &dateTime);

signals:
    /// Signal emitted when a variable has been created
    void variableCreated(std::shared_ptr<Variable> variable);

public slots:
    /**
     * Creates a new variable and adds it to the model
     * @param name the name of the new variable
     * @param provider the data provider for the new variable
     */
    void createVariable(const QString &name, std::shared_ptr<IDataProvider> provider) noexcept;

    void initialize();
    void finalize();

private:
    void waitForFinish();

    class VariableControllerPrivate;
    spimpl::unique_impl_ptr<VariableControllerPrivate> impl;
};

#endif // SCIQLOP_VARIABLECONTROLLER_H
