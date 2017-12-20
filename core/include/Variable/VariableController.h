#ifndef SCIQLOP_VARIABLECONTROLLER_H
#define SCIQLOP_VARIABLECONTROLLER_H

#include "CoreGlobal.h"

#include <Data/AcquisitionDataPacket.h>
#include <Data/SqpRange.h>

#include <QLoggingCategory>
#include <QObject>
#include <QUuid>

#include <Common/spimpl.h>

class IDataProvider;
class QItemSelectionModel;
class TimeController;
class Variable;
class VariableModel;

Q_DECLARE_LOGGING_CATEGORY(LOG_VariableController)


/**
 * Possible types of zoom operation
 */
enum class AcquisitionZoomType { ZoomOut, ZoomIn, PanRight, PanLeft, Unknown };


/**
 * @brief The VariableController class aims to handle the variables in SciQlop.
 */
class SCIQLOP_CORE_EXPORT VariableController : public QObject {
    Q_OBJECT
public:
    explicit VariableController(QObject *parent = 0);
    virtual ~VariableController();

    VariableModel *variableModel() noexcept;
    QItemSelectionModel *variableSelectionModel() noexcept;

    void setTimeController(TimeController *timeController) noexcept;

    /**
     * Clones the variable passed in parameter and adds the duplicate to the controller
     * @param variable the variable to duplicate
     * @return the duplicate created, nullptr if the variable couldn't be created
     */
    std::shared_ptr<Variable> cloneVariable(std::shared_ptr<Variable> variable) noexcept;

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

    /// Returns the MIME data associated to a list of variables
    QByteArray mimeDataForVariables(const QList<std::shared_ptr<Variable> > &variables) const;

    /// Returns the list of variables contained in a MIME data
    QList<std::shared_ptr<Variable> > variablesForMimeData(const QByteArray &mimeData) const;

    static AcquisitionZoomType getZoomType(const SqpRange &range, const SqpRange &oldRange);
signals:
    /// Signal emitted when a variable is about to be deleted from the controller
    void variableAboutToBeDeleted(std::shared_ptr<Variable> variable);

    /// Signal emitted when a data acquisition is requested on a range for a variable
    void rangeChanged(std::shared_ptr<Variable> variable, const SqpRange &range);

    /// Signal emitted when a sub range of the cacheRange of the variable can be displayed
    void updateVarDisplaying(std::shared_ptr<Variable> variable, const SqpRange &range);

    /// Signal emitted when all acquisitions related to the variables have been completed (whether
    /// validated, canceled, or failed)
    void acquisitionFinished();

public slots:
    /// Request the data loading of the variable whithin range
    void onRequestDataLoading(QVector<std::shared_ptr<Variable> > variables, const SqpRange &range,
                              bool synchronise);
    /**
     * Creates a new variable and adds it to the model
     * @param name the name of the new variable
     * @param metadata the metadata of the new variable
     * @param provider the data provider for the new variable
     * @return the pointer to the new variable or nullptr if the creation failed
     */
    std::shared_ptr<Variable> createVariable(const QString &name, const QVariantHash &metadata,
                                             std::shared_ptr<IDataProvider> provider) noexcept;

    /// Update the temporal parameters of every selected variable to dateTime
    void onDateTimeOnSelection(const SqpRange &dateTime);

    /// Update the temporal parameters of the specified variable
    void onUpdateDateTime(std::shared_ptr<Variable> variable, const SqpRange &dateTime);


    void onDataProvided(QUuid vIdentifier, const SqpRange &rangeRequested,
                        const SqpRange &cacheRangeRequested,
                        QVector<AcquisitionDataPacket> dataAcquired);

    void onVariableRetrieveDataInProgress(QUuid identifier, double progress);

    /// Cancel the current request for the variable
    void onAbortProgressRequested(std::shared_ptr<Variable> variable);
    void onAbortAcquisitionRequested(QUuid vIdentifier);

    // synchronization group methods
    void onAddSynchronizationGroupId(QUuid synchronizationGroupId);
    void onRemoveSynchronizationGroupId(QUuid synchronizationGroupId);
    void onAddSynchronized(std::shared_ptr<Variable> variable, QUuid synchronizationGroupId);

    /// Desynchronizes the variable of the group whose identifier is passed in parameter
    /// @remarks the method does nothing if the variable is not part of the group
    void desynchronize(std::shared_ptr<Variable> variable, QUuid synchronizationGroupId);

    void initialize();
    void finalize();

private:
    void waitForFinish();

    class VariableControllerPrivate;
    spimpl::unique_impl_ptr<VariableControllerPrivate> impl;
};

#endif // SCIQLOP_VARIABLECONTROLLER_H
