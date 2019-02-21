#ifndef SCIQLOP_CATALOGUEEVENTSMODEL_H
#define SCIQLOP_CATALOGUEEVENTSMODEL_H

#include <Common/spimpl.h>
#include <QAbstractItemModel>
#include <QLoggingCategory>
#include <unordered_set>
#include <vector>

#include <Catalogue/CatalogueController.h>

Q_DECLARE_LOGGING_CATEGORY(LOG_CatalogueEventsModel)

class CatalogueEventsModel : public QAbstractItemModel
{
    Q_OBJECT

signals:
    void modelSorted();

public:
    CatalogueEventsModel(QObject* parent = nullptr);

    enum class Column
    {
        Name,
        TStart,
        TEnd,
        Tags,
        Product,
        Validation,
        NbColumn
    };

    void setSourceCatalogues(const QVector<std::shared_ptr<DBCatalogue>>& catalogues);
    void setEvents(const std::vector<CatalogueController::Event_ptr>& events);
    void addEvent(const std::shared_ptr<DBEvent>& event);
    void removeEvent(const std::shared_ptr<DBEvent>& event);
    std::vector<CatalogueController::Event_ptr> events() const;

    enum class ItemType
    {
        Root,
        Event,
        EventProduct
    };
    ItemType itemTypeOf(const QModelIndex& index) const;
    CatalogueController::Event_ptr getEvent(const QModelIndex& index) const;
    CatalogueController::Event_ptr getParentEvent(const QModelIndex& index) const;
    std::optional<CatalogueController::Product_t> getEventProduct(const QModelIndex& index) const;

    /// Refresh the data for the specified event
    void refreshEvent(
        const CatalogueController::Event_ptr& event, bool refreshEventProducts = false);

    /// Returns a QModelIndex which represent the specified event
    QModelIndex indexOf(const CatalogueController::Event_ptr& event) const;

    /// Marks a change flag on the specified event to allow sorting on the validation column
    void setEventHasChanges(const std::shared_ptr<DBEvent>& event, bool hasChanges);

    /// Returns true if the specified event has unsaved changes
    bool eventsHasChanges(const std::shared_ptr<DBEvent>& event) const;

    // Model
    QModelIndex index(int row, int column, const QModelIndex& parent = QModelIndex()) const;
    QModelIndex parent(const QModelIndex& index) const;
    int rowCount(const QModelIndex& parent = QModelIndex()) const override;
    int columnCount(const QModelIndex& parent = QModelIndex()) const override;
    Qt::ItemFlags flags(const QModelIndex& index) const override;
    QVariant data(const QModelIndex& index, int role = Qt::DisplayRole) const override;
    QVariant headerData(
        int section, Qt::Orientation orientation, int role = Qt::DisplayRole) const override;
    void sort(int column, Qt::SortOrder order = Qt::AscendingOrder) override;

    Qt::DropActions supportedDragActions() const override;
    QStringList mimeTypes() const override;
    QMimeData* mimeData(const QModelIndexList& indexes) const override;

private:
    class CatalogueEventsModelPrivate;
    spimpl::unique_impl_ptr<CatalogueEventsModelPrivate> impl;
};

#endif // SCIQLOP_CATALOGUEEVENTSMODEL_H
