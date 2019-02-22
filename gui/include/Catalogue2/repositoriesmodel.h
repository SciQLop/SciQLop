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
#ifndef REPOSITORIESMODEL_H
#define REPOSITORIESMODEL_H
#include <Catalogue/CatalogueController.h>
#include <QAbstractItemModel>
#include <QIcon>
#include <QObject>

class RepositoriesModel : public QAbstractItemModel
{
    Q_OBJECT


    enum class ItemType
    {
        None,
        Catalogue,
        Repository
    };

    struct RepoModelItem
    {
        ItemType type;
        std::variant<QString, CatalogueController::Catalogue_ptr> item;
        RepoModelItem() : type { ItemType::None } {}
        RepoModelItem(const QString& repo);
        RepoModelItem(const CatalogueController::Catalogue_ptr& catalogue, RepoModelItem* parent)
                : type { ItemType::Catalogue }
                , item { catalogue }
                , parent { parent }
                , icon { ":/icones/catalogue.png" }
        {
        }
        QString repository() const { return std::get<QString>(item); }
        CatalogueController::Catalogue_ptr catalogue() const
        {
            return std::get<CatalogueController::Catalogue_ptr>(item);
        }
        QVariant data(int role) const;
        QString text() const
        {
            if (type == ItemType::Catalogue)
                return QString::fromStdString(catalogue()->name);
            if (type == ItemType::Repository)
                return repository();
            return QString();
        }
        std::vector<std::unique_ptr<RepoModelItem>> children;
        RepoModelItem* parent = nullptr;
        QIcon icon;
    };

    std::vector<std::unique_ptr<RepoModelItem>> _items;

    inline RepoModelItem* to_item(const QModelIndex& index) const
    {
        return static_cast<RepoModelItem*>(index.internalPointer());
    }

public:
    RepositoriesModel(QObject* parent = nullptr);

    ItemType type(const QModelIndex& index) const;

    Qt::ItemFlags flags(const QModelIndex& index) const override
    {
        return Qt::ItemIsEnabled | Qt::ItemIsSelectable | Qt::ItemIsDragEnabled;
    }

    QVariant data(const QModelIndex& index, int role = Qt::DisplayRole) const override;

    QModelIndex index(
        int row, int column, const QModelIndex& parent = QModelIndex()) const override;

    QModelIndex parent(const QModelIndex& index) const override;

    int rowCount(const QModelIndex& parent = QModelIndex()) const override;

    int columnCount(const QModelIndex& parent = QModelIndex()) const override { return 1; }
public slots:
    void refresh();
};

#endif // REPOSITORIESMODEL_H
