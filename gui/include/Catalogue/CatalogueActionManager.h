#ifndef SCIQLOP_CATALOGUEACTIONMANAGER_H
#define SCIQLOP_CATALOGUEACTIONMANAGER_H

#include <Common/spimpl.h>

class CatalogueExplorer;

class CatalogueActionManager {
public:
    CatalogueActionManager(CatalogueExplorer *catalogueExplorer);

    void installSelectionZoneActions();

private:
    class CatalogueActionManagerPrivate;
    spimpl::unique_impl_ptr<CatalogueActionManagerPrivate> impl;
};

#endif // SCIQLOP_CATALOGUEACTIONMANAGER_H
