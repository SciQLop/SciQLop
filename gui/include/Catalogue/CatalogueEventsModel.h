#ifndef SCIQLOP_CATALOGUEEVENTSMODEL_H
#define SCIQLOP_CATALOGUEEVENTSMODEL_H

#include <Common/spimpl.h>
#include <QAbstractItemModel>

class DBEvent;

class CatalogueEventsModel : public QAbstractItemModel {
public:
    CatalogueEventsModel(QObject *parent = nullptr);

    void setEvents(const QVector<std::shared_ptr<DBEvent> > &events);
    std::shared_ptr<DBEvent> getEvent(int row) const;


    void addEvent(const std::shared_ptr<DBEvent> &event);
    void removeEvent(const std::shared_ptr<DBEvent> &event);

    void refreshEvent(const std::shared_ptr<DBEvent> &event);

    // Model
    QModelIndex index(int row, int column, const QModelIndex &parent = QModelIndex()) const;
    QModelIndex parent(const QModelIndex &index) const;
    int rowCount(const QModelIndex &parent = QModelIndex()) const override;
    int columnCount(const QModelIndex &parent = QModelIndex()) const override;
    Qt::ItemFlags flags(const QModelIndex &index) const override;
    QVariant data(const QModelIndex &index, int role = Qt::DisplayRole) const override;
    QVariant headerData(int section, Qt::Orientation orientation,
                        int role = Qt::DisplayRole) const override;
    void sort(int column, Qt::SortOrder order = Qt::AscendingOrder) override;

    Qt::DropActions supportedDragActions() const override;
    QStringList mimeTypes() const override;
    QMimeData *mimeData(const QModelIndexList &indexes) const override;

private:
    class CatalogueEventsTableModelPrivate;
    spimpl::unique_impl_ptr<CatalogueEventsTableModelPrivate> impl;
};

#endif // SCIQLOP_CATALOGUEEVENTSMODEL_H
