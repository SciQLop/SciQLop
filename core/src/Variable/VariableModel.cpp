#include <Variable/Variable.h>
#include <Variable/VariableModel.h>

#include <Common/DateUtils.h>

#include <Data/IDataSeries.h>

#include <QSize>
#include <unordered_map>

Q_LOGGING_CATEGORY(LOG_VariableModel, "VariableModel")

namespace {

// Column indexes
const auto NAME_COLUMN = 0;
const auto TSTART_COLUMN = 1;
const auto TEND_COLUMN = 2;
const auto UNIT_COLUMN = 3;
const auto MISSION_COLUMN = 4;
const auto PLUGIN_COLUMN = 5;
const auto NB_COLUMNS = 6;

// Column properties
const auto DEFAULT_HEIGHT = 25;
const auto DEFAULT_WIDTH = 100;

struct ColumnProperties {
    ColumnProperties(const QString &name = {}, int width = DEFAULT_WIDTH,
                     int height = DEFAULT_HEIGHT)
            : m_Name{name}, m_Width{width}, m_Height{height}
    {
    }

    QString m_Name;
    int m_Width;
    int m_Height;
};

const auto COLUMN_PROPERTIES = QHash<int, ColumnProperties>{
    {NAME_COLUMN, {QObject::tr("Name")}},       {TSTART_COLUMN, {QObject::tr("tStart"), 180}},
    {TEND_COLUMN, {QObject::tr("tEnd"), 180}},  {UNIT_COLUMN, {QObject::tr("Unit")}},
    {MISSION_COLUMN, {QObject::tr("Mission")}}, {PLUGIN_COLUMN, {QObject::tr("Plugin")}}};

/// Format for datetimes
const auto DATETIME_FORMAT = QStringLiteral("dd/MM/yyyy \nhh:mm:ss:zzz");


} // namespace

struct VariableModel::VariableModelPrivate {
    /// Variables created in SciQlop
    std::vector<std::shared_ptr<Variable> > m_Variables;
    std::unordered_map<std::shared_ptr<Variable>, double> m_VariableToProgress;

    /// Return the row index of the variable. -1 if it's not found
    int indexOfVariable(Variable *variable) const noexcept;
};

VariableModel::VariableModel(QObject *parent)
        : QAbstractTableModel{parent}, impl{spimpl::make_unique_impl<VariableModelPrivate>()}
{
}

void VariableModel::addVariable(std::shared_ptr<Variable> variable) noexcept
{
    auto insertIndex = rowCount();
    beginInsertRows({}, insertIndex, insertIndex);

    impl->m_Variables.push_back(variable);
    connect(variable.get(), &Variable::updated, this, &VariableModel::onVariableUpdated);

    endInsertRows();
}

std::shared_ptr<Variable> VariableModel::createVariable(const QString &name,
                                                        const SqpRange &dateTime,
                                                        const QVariantHash &metadata) noexcept
{
    auto variable = std::make_shared<Variable>(name, dateTime, metadata);
    addVariable(variable);

    return variable;
}

void VariableModel::deleteVariable(std::shared_ptr<Variable> variable) noexcept
{
    if (!variable) {
        qCCritical(LOG_Variable()) << "Can't delete a null variable from the model";
        return;
    }

    // Finds variable in the model
    auto begin = impl->m_Variables.cbegin();
    auto end = impl->m_Variables.cend();
    auto it = std::find(begin, end, variable);
    if (it != end) {
        auto removeIndex = std::distance(begin, it);

        // Deletes variable
        beginRemoveRows({}, removeIndex, removeIndex);
        impl->m_Variables.erase(it);
        endRemoveRows();
    }
    else {
        qCritical(LOG_VariableModel())
            << tr("Can't delete variable %1 from the model: the variable is not in the model")
                   .arg(variable->name());
    }

    // Removes variable from progress map
    impl->m_VariableToProgress.erase(variable);
}


std::shared_ptr<Variable> VariableModel::variable(int index) const
{
    return (index >= 0 && index < impl->m_Variables.size()) ? impl->m_Variables[index] : nullptr;
}

std::vector<std::shared_ptr<Variable> > VariableModel::variables() const
{
    return impl->m_Variables;
}

void VariableModel::setDataProgress(std::shared_ptr<Variable> variable, double progress)
{
    if (progress > 0.0) {
        impl->m_VariableToProgress[variable] = progress;
    }
    else {
        impl->m_VariableToProgress.erase(variable);
    }
    auto modelIndex = createIndex(impl->indexOfVariable(variable.get()), NAME_COLUMN);

    emit dataChanged(modelIndex, modelIndex);
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
                case TSTART_COLUMN: {
                    auto range = variable->realRange();
                    return range != INVALID_RANGE
                               ? DateUtils::dateTime(range.m_TStart).toString(DATETIME_FORMAT)
                               : QVariant{};
                }
                case TEND_COLUMN: {
                    auto range = variable->realRange();
                    return range != INVALID_RANGE
                               ? DateUtils::dateTime(range.m_TEnd).toString(DATETIME_FORMAT)
                               : QVariant{};
                }
                case UNIT_COLUMN:
                    return variable->metadata().value(QStringLiteral("units"));
                case MISSION_COLUMN:
                    return variable->metadata().value(QStringLiteral("mission"));
                case PLUGIN_COLUMN:
                    return variable->metadata().value(QStringLiteral("plugin"));
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
    else if (role == VariableRoles::ProgressRole) {
        if (auto variable = impl->m_Variables.at(index.row())) {

            auto it = impl->m_VariableToProgress.find(variable);
            if (it != impl->m_VariableToProgress.cend()) {
                return it->second;
            }
        }
    }

    return QVariant{};
}

QVariant VariableModel::headerData(int section, Qt::Orientation orientation, int role) const
{
    if (role != Qt::DisplayRole && role != Qt::SizeHintRole) {
        return QVariant{};
    }

    if (orientation == Qt::Horizontal) {
        auto propertiesIt = COLUMN_PROPERTIES.find(section);
        if (propertiesIt != COLUMN_PROPERTIES.cend()) {
            // Role is either DisplayRole or SizeHintRole
            return (role == Qt::DisplayRole)
                       ? QVariant{propertiesIt->m_Name}
                       : QVariant{QSize{propertiesIt->m_Width, propertiesIt->m_Height}};
        }
        else {
            qWarning(LOG_VariableModel())
                << tr("Can't get header data (unknown column %1)").arg(section);
        }
    }

    return QVariant{};
}

void VariableModel::abortProgress(const QModelIndex &index)
{
    if (auto variable = impl->m_Variables.at(index.row())) {
        emit abortProgessRequested(variable);
    }
}

void VariableModel::onVariableUpdated() noexcept
{
    // Finds variable that has been updated in the model
    if (auto updatedVariable = dynamic_cast<Variable *>(sender())) {
        auto updatedVariableIndex = impl->indexOfVariable(updatedVariable);

        if (updatedVariableIndex > -1) {
            emit dataChanged(createIndex(updatedVariableIndex, 0),
                             createIndex(updatedVariableIndex, columnCount() - 1));
        }
    }
}

int VariableModel::VariableModelPrivate::indexOfVariable(Variable *variable) const noexcept
{
    auto begin = std::cbegin(m_Variables);
    auto end = std::cend(m_Variables);
    auto it
        = std::find_if(begin, end, [variable](const auto &var) { return var.get() == variable; });

    if (it != end) {
        // Gets the index of the variable in the model: we assume here that views have the same
        // order as the model
        return std::distance(begin, it);
    }
    else {
        return -1;
    }
}
