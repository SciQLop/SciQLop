/*
    This file is part of SciQLop.

    SciQLop is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    SciQLop is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with SciQLop.  If not, see <https://www.gnu.org/licenses/>.
*/
#ifndef EVENTSMODEL_H
#define EVENTSMODEL_H
#include <Catalogue/CatalogueController.h>
#include <QAbstractItemModel>
#include <array>

class EventsModel : public QAbstractItemModel
{
    Q_OBJECT
    std::vector<CatalogueController::Event_ptr> _events;

    enum class ItemType
    {
        None,
        Event,
        Product
    };

    enum class Columns
    {
        Name = 0,
        TStart = 1,
        TEnd = 2,
        Tags = 3,
        Product = 4,
        Validation = 5,
        NbColumn = 6
    };

    const std::array<QString, static_cast<int>(Columns::NbColumn)> ColumnsNames
        = { "Name", "Start time", "Stop time", "Tags", "Product(s)", "" };


public:
    EventsModel(QObject* parent = nullptr);


    ItemType type(const QModelIndex& index) const;

    Qt::ItemFlags flags(const QModelIndex& index) const override
    {
        return Qt::ItemIsEnabled | Qt::ItemIsSelectable | Qt::ItemIsDragEnabled;
    }
    QVariant data(int col, const CatalogueController::Event_ptr& event) const;
    QVariant data(int col, const CatalogueController::Product_t& product) const;
    QVariant data(const QModelIndex& index, int role = Qt::DisplayRole) const override;

    QModelIndex index(
        int row, int column, const QModelIndex& parent = QModelIndex()) const override;

    QModelIndex parent(const QModelIndex& index) const override;

    int rowCount(const QModelIndex& parent = QModelIndex()) const override;

    int columnCount(const QModelIndex& parent = QModelIndex()) const override;

    QVariant headerData(
        int section, Qt::Orientation orientation, int role = Qt::DisplayRole) const override;

    void sort(int column, Qt::SortOrder order = Qt::AscendingOrder) override;

public slots:
    void setEvents(std::vector<CatalogueController::Event_ptr> events)
    {
        beginResetModel();
        std::swap(_events, events);
        endResetModel();
    }
};

#endif // EVENTSMODEL_H
