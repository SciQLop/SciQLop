#ifndef SCIQLOP_VARIABLEMODEL_H
#define SCIQLOP_VARIABLEMODEL_H


#include <Data/SqpDateTime.h>

#include <QAbstractTableModel>
#include <QLoggingCategory>

#include <Common/MetaTypes.h>
#include <Common/spimpl.h>

Q_DECLARE_LOGGING_CATEGORY(LOG_VariableModel)

enum VariableRoles { ProgressRole = Qt::UserRole };


class IDataSeries;
class Variable;

/**
 * @brief The VariableModel class aims to hold the variables that have been created in SciQlop
 */
class VariableModel : public QAbstractTableModel {
public:
    explicit VariableModel(QObject *parent = nullptr);

    /**
     * Creates a new variable in the model
     * @param name the name of the new variable
     * @param dateTime the dateTime of the new variable
     * @return the pointer to the new variable
     */
    std::shared_ptr<Variable> createVariable(const QString &name,
                                             const SqpDateTime &dateTime) noexcept;

    /**
     * Deletes a variable from the model, if it exists
     * @param variable the variable to delete
     */
    void deleteVariable(std::shared_ptr<Variable> variable) noexcept;


    std::shared_ptr<Variable> variable(int index) const;

    void setDataProgress(std::shared_ptr<Variable> variable, double progress);

    // /////////////////////////// //
    // QAbstractTableModel methods //
    // /////////////////////////// //

    virtual int columnCount(const QModelIndex &parent = QModelIndex{}) const override;
    virtual int rowCount(const QModelIndex &parent = QModelIndex{}) const override;
    virtual QVariant data(const QModelIndex &index, int role = Qt::DisplayRole) const override;
    virtual QVariant headerData(int section, Qt::Orientation orientation,
                                int role = Qt::DisplayRole) const override;

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
