#include <Variable/VariableModel.h>

#include <Variable/Variable.h>

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
    std::vector<std::unique_ptr<Variable> > m_Variables;
};

VariableModel::VariableModel(QObject *parent)
        : QAbstractTableModel{parent}, impl{spimpl::make_unique_impl<VariableModelPrivate>()}
{
}

Variable *VariableModel::createVariable(const QString &name) noexcept
{
    /// @todo For the moment, the other data of the variable is initialized with default values
    auto variable
        = std::make_unique<Variable>(name, QStringLiteral("unit"), QStringLiteral("mission"));
    impl->m_Variables.push_back(std::move(variable));

    return impl->m_Variables.back().get();
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
