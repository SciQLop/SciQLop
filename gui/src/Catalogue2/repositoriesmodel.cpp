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
#include <Catalogue2/repositoriesmodel.h>
#include <Common/containers.h>
#include <SqpApplication.h>


RepositoriesModel::RepositoriesModel(QObject* parent) : QAbstractItemModel(parent)
{
    refresh();
}

RepositoriesModel::ItemType RepositoriesModel::type(const QModelIndex& index) const
{
    if (RepoModelItem* item = to_item(index))
    {
        return item->type;
    }
    return ItemType::None;
}

void RepositoriesModel::refresh()
{
    beginResetModel();
    _items.clear();
    _items.push_back(std::make_unique<RepoModelItem>("All"));
    _items.push_back(std::make_unique<RepoModelItem>("Trash"));
    auto repo_list = sqpApp->catalogueController().repositories();
    std::transform(std::begin(repo_list), std::end(repo_list), std::back_inserter(_items),
        [](const auto& repo_name) { return std::make_unique<RepoModelItem>(repo_name); });
    endResetModel();
}

QVariant RepositoriesModel::data(const QModelIndex& index, int role) const
{
    if (index.isValid() && index.column() == 0)
    {
        return to_item(index)->data(role);
    }
    return QVariant {};
}

QModelIndex RepositoriesModel::index(int row, int column, const QModelIndex& parent) const
{
    if (!hasIndex(row, column, parent))
    {
        return QModelIndex();
    }

    switch (type(parent))
    {
        case RepositoriesModel::ItemType::None: // is a repo
            return createIndex(row, column, _items[row].get());
        case RepositoriesModel::ItemType::Repository: // is a catalogue
            return createIndex(row, column, to_item(parent)->children[row].get());
        case RepositoriesModel::ItemType::Catalogue:
            return createIndex(row, column, new RepoModelItem());
    }

    return QModelIndex();
}

QModelIndex RepositoriesModel::parent(const QModelIndex& index) const
{
    auto item = to_item(index);
    if (item->type == ItemType::Catalogue)
    {
        auto repoIndex = SciQLop::containers::index_of(_items, item->parent);
        return createIndex(repoIndex, 0, item->parent);
    }
    return QModelIndex();
}

int RepositoriesModel::rowCount(const QModelIndex& parent) const
{
    switch (type(parent))
    {
        case RepositoriesModel::ItemType::None:
            return _items.size();
        case RepositoriesModel::ItemType::Repository:
            return to_item(parent)->children.size();
        case RepositoriesModel::ItemType::Catalogue:
            break;
    }
    return 0;
}

RepositoriesModel::RepoModelItem::RepoModelItem(const QString& repo)
        : type { ItemType::Repository }, item { repo }, icon { ":/icones/database.png" }
{
    auto catalogues = sqpApp->catalogueController().catalogues(repo);
    std::transform(std::begin(catalogues), std::end(catalogues), std::back_inserter(children),
        [this](auto& catalogue) { return std::make_unique<RepoModelItem>(catalogue, this); });
}

QVariant RepositoriesModel::RepoModelItem::data(int role) const
{
    switch (role)
    {
        case Qt::EditRole:
        case Qt::DisplayRole:
            return text();
        case Qt::DecorationRole:
            return QVariant { icon };
        default:
            break;
    }
    return QVariant {};
}
