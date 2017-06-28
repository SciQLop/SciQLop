#include <Variable/Variable.h>
#include <Variable/VariableModel.h>

#include <Data/IDataSeries.h>

Q_LOGGING_CATEGORY(LOG_VariableModel, "VariableModel")

namespace {

// Column indexes
const auto NAME_COLUMN = 0;
const auto UNIT_COLUMN = 1;
const auto MISSION_COLUMN = 2;
const auto NB_COLUMNS = 3;

} // namespace

struct VariableModel::VariableModelPrivate {
    /// Variables created in SciQlop
    std::vector<std::shared_ptr<Variable> > m_Variables;
};

VariableModel::VariableModel(QObject *parent)
        : QAbstractTableModel{parent}, impl{spimpl::make_unique_impl<VariableModelPrivate>()}
{
}

std::shared_ptr<Variable>
VariableModel::createVariable(const QString &name, const SqpDateTime &dateTime,
                              std::unique_ptr<IDataSeries> defaultDataSeries) noexcept
{
    auto insertIndex = rowCount();
    beginInsertRows({}, insertIndex, insertIndex);

    /// @todo For the moment, the other data of the variable is initialized with default values
    auto variable = std::make_shared<Variable>(name, QStringLiteral("unit"),
                                               QStringLiteral("mission"), dateTime);
    variable->setDataSeries(std::move(defaultDataSeries));

    impl->m_Variables.push_back(variable);

    endInsertRows();

    return variable;
}

std::shared_ptr<Variable> VariableModel::variable(int index) const
{
    return (index >= 0 && index < impl->m_Variables.size()) ? impl->m_Variables.at(index) : nullptr;
}

int VariableModel::columnCount(const QModelIndex &parent) const
{
    Q_UNUSED(parent);

    return NB_COLUMNS;
}

int VariableModel::rowCount(const QModelIndex &parent) const
{
    Q_UNUSED(parent);

    return impl->m_Variables.size();
}

QVariant VariableModel::data(const QModelIndex &index, int role) const
{
    if (!index.isValid()) {
        return QVariant{};
    }

    if (index.row() < 0 || index.row() >= rowCount()) {
        return QVariant{};
    }

    if (role == Qt::DisplayRole) {
        if (auto variable = impl->m_Variables.at(index.row()).get()) {
            switch (index.column()) {
                case NAME_COLUMN:
                    return variable->name();
                case UNIT_COLUMN:
                    return variable->unit();
                case MISSION_COLUMN:
                    return variable->mission();
                default:
                    // No action
                    break;
            }

            qWarning(LOG_VariableModel())
                << tr("Can't get data (unknown column %1)").arg(index.column());
        }
        else {
            qWarning(LOG_VariableModel()) << tr("Can't get data (no variable)");
        }
    }

    return QVariant{};
}

QVariant VariableModel::headerData(int section, Qt::Orientation orientation, int role) const
{
    if (role != Qt::DisplayRole) {
        return QVariant{};
    }

    if (orientation == Qt::Horizontal) {
        switch (section) {
            case NAME_COLUMN:
                return tr("Name");
            case UNIT_COLUMN:
                return tr("Unit");
            case MISSION_COLUMN:
                return tr("Mission");
            default:
                // No action
                break;
        }

        qWarning(LOG_VariableModel())
            << tr("Can't get header data (unknown column %1)").arg(section);
    }

    return QVariant{};
}
