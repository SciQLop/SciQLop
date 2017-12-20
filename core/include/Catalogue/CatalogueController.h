#ifndef SCIQLOP_CATALOGUECONTROLLER_H
#define SCIQLOP_CATALOGUECONTROLLER_H

#include "CoreGlobal.h"

#include <Data/SqpRange.h>

#include <QLoggingCategory>
#include <QObject>
#include <QUuid>

#include <Common/spimpl.h>

#include <memory>

class DBCatalogue;
class DBEvent;
class DBEventProduct;

Q_DECLARE_LOGGING_CATEGORY(LOG_CatalogueController)

class DataSourceItem;
class Variable;

/**
 * @brief The CatalogueController class aims to handle catalogues and event using the CatalogueAPI
 * library.
 */
class SCIQLOP_CORE_EXPORT CatalogueController : public QObject {
    Q_OBJECT
public:
    explicit CatalogueController(QObject *parent = 0);
    virtual ~CatalogueController();

    // DB
    QStringList getRepositories() const;
    void addDB(const QString &dbPath);
    void saveDB(const QString &destinationPath, const QString &repository);

    // Event
    /// retrieveEvents with empty repository retrieve them from the default repository
    std::list<std::shared_ptr<DBEvent> > retrieveEvents(const QString &repository) const;
    std::list<std::shared_ptr<DBEvent> > retrieveAllEvents() const;
    std::list<std::shared_ptr<DBEvent> >
    retrieveEventsFromCatalogue(std::shared_ptr<DBCatalogue> catalogue) const;
    void addEvent(std::shared_ptr<DBEvent> event);
    void updateEvent(std::shared_ptr<DBEvent> event);
    void updateEventProduct(std::shared_ptr<DBEventProduct> eventProduct);
    void removeEvent(std::shared_ptr<DBEvent> event);
    //    void trashEvent(std::shared_ptr<DBEvent> event);
    //        void restore(std::shared_ptr<DBEvent> event);
    void saveEvent(std::shared_ptr<DBEvent> event);
    void discardEvent(std::shared_ptr<DBEvent> event);
    bool eventHasChanges(std::shared_ptr<DBEvent> event) const;

    // Catalogue
    //    bool createCatalogue(const QString &name, QVector<QUuid> eventList);
    /// retrieveEvents with empty repository retrieve them from the default repository
    std::list<std::shared_ptr<DBCatalogue> > retrieveCatalogues(const QString &repository
                                                                = QString()) const;
    void updateCatalogue(std::shared_ptr<DBCatalogue> catalogue);
    void removeCatalogue(std::shared_ptr<DBCatalogue> catalogue);
    void saveCatalogue(std::shared_ptr<DBCatalogue> catalogue);

    void saveAll();
    bool hasChanges() const;

    /// Returns the MIME data associated to a list of variables
    QByteArray mimeDataForEvents(const QVector<std::shared_ptr<DBEvent> > &events) const;

    /// Returns the list of variables contained in a MIME data
    QVector<std::shared_ptr<DBEvent> > eventsForMimeData(const QByteArray &mimeData) const;

public slots:
    /// Manage init/end of the controller
    void initialize();

private:
    class CatalogueControllerPrivate;
    spimpl::unique_impl_ptr<CatalogueControllerPrivate> impl;
};

#endif // SCIQLOP_CATALOGUECONTROLLER_H
