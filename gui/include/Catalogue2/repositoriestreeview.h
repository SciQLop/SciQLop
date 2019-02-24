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
#ifndef REPOSITORIESTREEVIEW_H
#define REPOSITORIESTREEVIEW_H

#include <Catalogue2/repositoriesmodel.h>
#include <QObject>
#include <QTreeView>

class RepositoriesTreeView : public QTreeView
{
    Q_OBJECT
public:
    RepositoriesTreeView(QWidget* parent = nullptr);

public slots:
    void refresh() { static_cast<RepositoriesModel*>(model())->refresh(); }

signals:
    void repositorySelected(const QString& repository);
    void catalogueSelected(const CatalogueController::Catalogue_ptr& catalogue);

private:
    void _itemSelected(const QModelIndex& index)
    {
        auto item = RepositoriesModel::to_item(index);
        if (item->type == RepositoriesModel::ItemType::Repository)
        {
            emit repositorySelected(item->repository());
        }
        else if (item->type == RepositoriesModel::ItemType::Catalogue)
        {
            emit catalogueSelected(item->catalogue());
        }
    }
};

#endif // REPOSITORIESTREEVIEW_H
