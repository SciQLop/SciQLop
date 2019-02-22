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
#include <Catalogue2/repositoriestreeview.h>

RepositoriesTreeView::RepositoriesTreeView(QWidget* parent) : QTreeView(parent)
{
    auto m = model();
    this->setModel(new RepositoriesModel(this));
    delete m;
}


