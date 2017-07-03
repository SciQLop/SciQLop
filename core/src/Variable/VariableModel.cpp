#include <Variable/Variable.h>
#include <Variable/VariableModel.h>

#include <Data/IDataSeries.h>

#include <QDateTime>
#include <QSize>

Q_LOGGING_CATEGORY(LOG_VariableModel, "VariableModel")

namespace {

// Column indexes
const auto NAME_COLUMN = 0;
const auto TSTART_COLUMN = 1;
const auto TEND_COLUMN = 2;
const auto NB_COLUMNS = 3;

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

const auto COLUMN_PROPERTIES
    = QHash<int, ColumnProperties>{{NAME_COLUMN, {QObject::tr("Name")}},
                                   {TSTART_COLUMN, {QObject::tr("tStart"), 180}},
                                   {TEND_COLUMN, {QObject::tr("tEnd"), 180}}};

/// Format for datetimes
const auto DATETIME_FORMAT = QStringLiteral("dd/MM/yyyy \nhh:mm:ss:zzz");

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
                              std::shared_ptr<IDataSeries> defaultDataSeries) noexcept
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
    return (index >= 0 && index < impl->m_Variables.size()) ? impl->m_Variables[index] : nullptr;
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
            /// Lambda function that builds the variant to return for a time value
            auto dateTimeVariant = [](double time) {
                auto dateTime = QDateTime::fromMSecsSinceEpoch(time * 1000.);
                return dateTime.toString(DATETIME_FORMAT);
            };

            switch (index.column()) {
                case NAME_COLUMN:
                    return variable->name();
                case TSTART_COLUMN:
                    return dateTimeVariant(variable->dateTime().m_TStart);
                case TEND_COLUMN:
                    return dateTimeVariant(variable->dateTime().m_TEnd);
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
