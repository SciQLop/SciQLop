#ifndef SCIQLOP_VARIABLEMODEL_H
#define SCIQLOP_VARIABLEMODEL_H

#include "CoreGlobal.h"

#include <Data/SqpRange.h>

#include <QAbstractTableModel>
#include <QLoggingCategory>

#include <Common/MetaTypes.h>
#include <Common/spimpl.h>

Q_DECLARE_LOGGING_CATEGORY(LOG_VariableModel)

enum VariableRoles { ProgressRole = Qt::UserRole };


class IDataSeries;
class Variable;
class VariableController;

/**
 * @brief The VariableModel class aims to hold the variables that have been created in SciQlop
 */
class SCIQLOP_CORE_EXPORT VariableModel : public QAbstractTableModel {
    Q_OBJECT
public:
    explicit VariableModel(VariableController *parent = nullptr);

    /**
     * Adds an existing variable in the model.
     * @param variable the variable to add.
     * @remarks the variable's name is modified to avoid name duplicates
     * @remarks this method does nothing if the variable already exists in the model
     */
    void addVariable(std::shared_ptr<Variable> variable) noexcept;

    /**
     * Checks that a variable is contained in the model
     * @param variable the variable to check
     * @return true if the variable is in the model, false otherwise
     */
    bool containsVariable(std::shared_ptr<Variable> variable) const noexcept;

    /**
     * Creates a new variable in the model
     * @param name the name of the new variable
     * @param metadata the metadata associated to the new variable
     * @return the pointer to the new variable
     */
    std::shared_ptr<Variable> createVariable(const QString &name,
                                             const QVariantHash &metadata) noexcept;

    /**
     * Deletes a variable from the model, if it exists
     * @param variable the variable to delete
     */
    void deleteVariable(std::shared_ptr<Variable> variable) noexcept;


    std::shared_ptr<Variable> variable(int index) const;
    std::vector<std::shared_ptr<Variable> > variables() const;

    void setDataProgress(std::shared_ptr<Variable> variable, double progress);


    // /////////////////////////// //
    // QAbstractTableModel methods //
    // /////////////////////////// //

    virtual int columnCount(const QModelIndex &parent = QModelIndex{}) const override;
    virtual int rowCount(const QModelIndex &parent = QModelIndex{}) const override;
    virtual QVariant data(const QModelIndex &index, int role = Qt::DisplayRole) const override;
    virtual QVariant headerData(int section, Qt::Orientation orientation,
                                int role = Qt::DisplayRole) const override;
    virtual Qt::ItemFlags flags(const QModelIndex &index) const override;

    // ///////////////// //
    // Drag&Drop methods //
    // ///////////////// //

    virtual Qt::DropActions supportedDropActions() const override;
    virtual Qt::DropActions supportedDragActions() const override;
    virtual QStringList mimeTypes() const override;
    virtual QMimeData *mimeData(const QModelIndexList &indexes) const override;
    virtual bool canDropMimeData(const QMimeData *data, Qt::DropAction action, int row, int column,
                                 const QModelIndex &parent) const override;
    virtual bool dropMimeData(const QMimeData *data, Qt::DropAction action, int row, int column,
                              const QModelIndex &parent) override;

    void abortProgress(const QModelIndex &index);

signals:
    void abortProgessRequested(std::shared_ptr<Variable> variable);
    void requestVariable(const QVariantHash &productData);
    void requestVariableRangeUpdate(std::shared_ptr<Variable> variable, const DateTimeRange &range);

private:
    class VariableModelPrivate;
    spimpl::unique_impl_ptr<VariableModelPrivate> impl;

private slots:
    /// Slot called when data of a variable has been updated
    void onVariableUpdated() noexcept;
};

// Registers QVector<int> metatype so it can be used in VariableModel::dataChanged() signal
SCIQLOP_REGISTER_META_TYPE(QVECTOR_INT_REGISTRY, QVector<int>)

#endif // SCIQLOP_VARIABLEMODEL_H
