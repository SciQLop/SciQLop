#include <Variable/Variable.h>
#include <Variable/VariableController.h>
#include <Variable/VariableModel.h>

#include <Common/DateUtils.h>
#include <Common/MimeTypesDef.h>
#include <Common/StringUtils.h>

#include <Data/IDataSeries.h>

#include <DataSource/DataSourceController.h>
#include <Time/TimeController.h>

#include <QMimeData>
#include <QSize>
#include <QTimer>
#include <unordered_map>

Q_LOGGING_CATEGORY(LOG_VariableModel, "VariableModel")

namespace {

// Column indexes
const auto NAME_COLUMN = 0;
const auto TSTART_COLUMN = 1;
const auto TEND_COLUMN = 2;
const auto NBPOINTS_COLUMN = 3;
const auto UNIT_COLUMN = 4;
const auto MISSION_COLUMN = 5;
const auto PLUGIN_COLUMN = 6;
const auto NB_COLUMNS = 7;

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
    {NAME_COLUMN, {QObject::tr("Name")}},      {TSTART_COLUMN, {QObject::tr("tStart"), 180}},
    {TEND_COLUMN, {QObject::tr("tEnd"), 180}}, {NBPOINTS_COLUMN, {QObject::tr("Nb points")}},
    {UNIT_COLUMN, {QObject::tr("Unit")}},      {MISSION_COLUMN, {QObject::tr("Mission")}},
    {PLUGIN_COLUMN, {QObject::tr("Plugin")}}};

QString uniqueName(const QString &defaultName,
                   const std::vector<std::shared_ptr<Variable> > &variables)
{
    auto forbiddenNames = std::vector<QString>(variables.size());
    std::transform(variables.cbegin(), variables.cend(), forbiddenNames.begin(),
                   [](const auto &variable) { return variable->name(); });
    auto uniqueName = StringUtils::uniqueName(defaultName, forbiddenNames);
    Q_ASSERT(!uniqueName.isEmpty());

    return uniqueName;
}

} // namespace

struct VariableModel::VariableModelPrivate {
    /// Variables created in SciQlop
    std::vector<std::shared_ptr<Variable> > m_Variables;
    std::unordered_map<std::shared_ptr<Variable>, double> m_VariableToProgress;
    VariableController *m_VariableController;

    /// Return the row index of the variable. -1 if it's not found
    int indexOfVariable(Variable *variable) const noexcept;
};

VariableModel::VariableModel(VariableController *parent)
        : QAbstractTableModel{parent}, impl{spimpl::make_unique_impl<VariableModelPrivate>()}
{
    impl->m_VariableController = parent;
}

void VariableModel::addVariable(std::shared_ptr<Variable> variable) noexcept
{
    auto insertIndex = rowCount();
    beginInsertRows({}, insertIndex, insertIndex);

    // Generates unique name for the variable
    variable->setName(uniqueName(variable->name(), impl->m_Variables));

    impl->m_Variables.push_back(variable);
    connect(variable.get(), &Variable::updated, this, &VariableModel::onVariableUpdated);

    endInsertRows();
}

bool VariableModel::containsVariable(std::shared_ptr<Variable> variable) const noexcept
{
    auto end = impl->m_Variables.cend();
    return std::find(impl->m_Variables.cbegin(), end, variable) != end;
}

std::shared_ptr<Variable> VariableModel::createVariable(const QString &name,
                                                        const QVariantHash &metadata) noexcept
{
    auto variable = std::make_shared<Variable>(name, metadata);
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
    return (index >= 0u && static_cast<size_t>(index) < impl->m_Variables.size())
               ? impl->m_Variables[index]
               : nullptr;
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
                case NBPOINTS_COLUMN:
                    return variable->nbPoints();
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

Qt::ItemFlags VariableModel::flags(const QModelIndex &index) const
{
    return QAbstractTableModel::flags(index) | Qt::ItemIsDragEnabled | Qt::ItemIsDropEnabled;
}

Qt::DropActions VariableModel::supportedDropActions() const
{
    return Qt::CopyAction | Qt::MoveAction;
}

Qt::DropActions VariableModel::supportedDragActions() const
{
    return Qt::CopyAction | Qt::MoveAction;
}

QStringList VariableModel::mimeTypes() const
{
    return {MIME_TYPE_VARIABLE_LIST, MIME_TYPE_TIME_RANGE};
}

QMimeData *VariableModel::mimeData(const QModelIndexList &indexes) const
{
    auto mimeData = new QMimeData;

    QList<std::shared_ptr<Variable> > variableList;


    DateTimeRange firstTimeRange;
    for (const auto &index : indexes) {
        if (index.column() == 0) { // only the first column
            auto variable = impl->m_Variables.at(index.row());
            if (variable.get() && index.isValid()) {

                if (variableList.isEmpty()) {
                    // Gets the range of the first variable
                    firstTimeRange = std::move(variable->range());
                }

                variableList << variable;
            }
        }
    }

    auto variablesEncodedData = impl->m_VariableController->mimeDataForVariables(variableList);
    mimeData->setData(MIME_TYPE_VARIABLE_LIST, variablesEncodedData);

    if (variableList.count() == 1) {
        // No time range MIME data if multiple variables are dragged
        auto timeEncodedData = TimeController::mimeDataForTimeRange(firstTimeRange);
        mimeData->setData(MIME_TYPE_TIME_RANGE, timeEncodedData);
    }

    return mimeData;
}

bool VariableModel::canDropMimeData(const QMimeData *data, Qt::DropAction action, int row,
                                    int column, const QModelIndex &parent) const
{
    // drop of a product
    return data->hasFormat(MIME_TYPE_PRODUCT_LIST)
           || (data->hasFormat(MIME_TYPE_TIME_RANGE) && parent.isValid()
               && !data->hasFormat(MIME_TYPE_VARIABLE_LIST));
}

bool VariableModel::dropMimeData(const QMimeData *data, Qt::DropAction action, int row, int column,
                                 const QModelIndex &parent)
{
    auto dropDone = false;

    if (data->hasFormat(MIME_TYPE_PRODUCT_LIST)) {

        auto productList
            = DataSourceController::productsDataForMimeData(data->data(MIME_TYPE_PRODUCT_LIST));

        for (auto metaData : productList) {
            emit requestVariable(metaData.toHash());
        }

        dropDone = true;
    }
    else if (data->hasFormat(MIME_TYPE_TIME_RANGE) && parent.isValid()) {
        auto variable = this->variable(parent.row());
        auto range = TimeController::timeRangeForMimeData(data->data(MIME_TYPE_TIME_RANGE));

        emit requestVariableRangeUpdate(variable, range);

        dropDone = true;
    }

    return dropDone;
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
