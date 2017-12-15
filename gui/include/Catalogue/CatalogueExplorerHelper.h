#ifndef SCIQLOP_CATALOGUEEXPLORERHELPER_H
#define SCIQLOP_CATALOGUEEXPLORERHELPER_H

#include <QWidget>

#include <functional>

struct CatalogueExplorerHelper {
    static QWidget *buildValidationWidget(QWidget *parent, std::function<void()> save,
                                          std::function<void()> discard);
};

#endif // SCIQLOP_CATALOGUEEXPLORERHELPER_H
