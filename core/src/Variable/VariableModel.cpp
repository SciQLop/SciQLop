#include <Variable/VariableModel.h>

#include <Variable/Variable.h>

Q_LOGGING_CATEGORY(LOG_VariableModel, "VariableModel")

namespace {

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

    return QVariant{};
}
