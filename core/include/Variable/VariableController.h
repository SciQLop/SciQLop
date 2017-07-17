#ifndef SCIQLOP_VARIABLECONTROLLER_H
#define SCIQLOP_VARIABLECONTROLLER_H

#include <Data/SqpDateTime.h>

#include <QLoggingCategory>
#include <QObject>

#include <Common/spimpl.h>

class IDataProvider;
class QItemSelectionModel;
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
    QItemSelectionModel *variableSelectionModel() noexcept;

    void setTimeController(TimeController *timeController) noexcept;

    /**
     * Deletes from the controller the variable passed in parameter.
     *
     * Delete a variable includes:
     * - the deletion of the various references to the variable in SciQlop
     * - the deletion of the model variable
     * - the deletion of the provider associated with the variable
     * - removing the cache associated with the variable
     *
     * @param variable the variable to delete from the controller.
     */
    void deleteVariable(std::shared_ptr<Variable> variable) noexcept;

    /**
     * Deletes from the controller the variables passed in parameter.
     * @param variables the variables to delete from the controller.
     * @sa deleteVariable()
     */
    void deleteVariables(const QVector<std::shared_ptr<Variable> > &variables) noexcept;

    /**
     * @brief abort the variable retrieve data progression
     */
    void abortProgress(std::shared_ptr<Variable> variable);

signals:
    /// Signal emitted when a variable is about to be deleted from the controller
    void variableAboutToBeDeleted(std::shared_ptr<Variable> variable);

public slots:
    /// Request the data loading of the variable whithin dateTime
    void onRequestDataLoading(std::shared_ptr<Variable> variable, const SqpDateTime &dateTime);
    /**
     * Creates a new variable and adds it to the model
     * @param name the name of the new variable
     * @param metadata the metadata of the new variable
     * @param provider the data provider for the new variable
     */
    void createVariable(const QString &name, const QVariantHash &metadata,
                        std::shared_ptr<IDataProvider> provider) noexcept;

    /// Update the temporal parameters of every selected variable to dateTime
    void onDateTimeOnSelection(const SqpDateTime &dateTime);


    void onVariableRetrieveDataInProgress(QUuid identifier, double progress);

    void onAbortProgressRequested(std::shared_ptr<Variable> variable);

    void initialize();
    void finalize();

private:
    void waitForFinish();

    class VariableControllerPrivate;
    spimpl::unique_impl_ptr<VariableControllerPrivate> impl;
};

#endif // SCIQLOP_VARIABLECONTROLLER_H
