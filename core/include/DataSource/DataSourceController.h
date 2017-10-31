#ifndef SCIQLOP_DATASOURCECONTROLLER_H
#define SCIQLOP_DATASOURCECONTROLLER_H

#include "CoreGlobal.h"

#include <QLoggingCategory>
#include <QObject>
#include <QUuid>

#include <Common/spimpl.h>

Q_DECLARE_LOGGING_CATEGORY(LOG_DataSourceController)

class DataSourceItem;
class IDataProvider;

/**
 * @brief The DataSourceController class aims to make the link between SciQlop and its plugins. This
 * is the intermediate class that SciQlop has to use in the way to connect a data source. Please
 * first use register method to initialize a plugin specified by its metadata name (JSON plugin
 * source) then others specifics method will be able to access it. You can load a data source driver
 * plugin then create a data source.
 */
class SCIQLOP_CORE_EXPORT DataSourceController : public QObject {
    Q_OBJECT
public:
    explicit DataSourceController(QObject *parent = 0);
    virtual ~DataSourceController();

    /**
     * Registers a data source. The method delivers a unique id that can be used afterwards to
     * access to the data source properties (structure, connection parameters, data provider, etc.)
     * @param dataSourceName the name of the data source
     * @return the unique id with which the data source has been registered
     */
    QUuid registerDataSource(const QString &dataSourceName) noexcept;

    /**
     * Sets the structure of a data source. The controller takes ownership of the structure.
     * @param dataSourceUid the unique id with which the data source has been registered into the
     * controller. If it is invalid, the method has no effect.
     * @param dataSourceItem the structure of the data source. It must be not null to be registered
     * @sa registerDataSource()
     */
    void setDataSourceItem(const QUuid &dataSourceUid,
                           std::unique_ptr<DataSourceItem> dataSourceItem) noexcept;

    /**
     * Sets the data provider used to retrieve data from of a data source. The controller takes
     * ownership of the provider.
     * @param dataSourceUid the unique id with which the data source has been registered into the
     * controller. If it is invalid, the method has no effect.
     * @param dataProvider the provider of the data source
     * @sa registerDataSource()
     */
    void setDataProvider(const QUuid &dataSourceUid,
                         std::unique_ptr<IDataProvider> dataProvider) noexcept;

    /**
     * Loads an item (product) as a variable in SciQlop
     * @param dataSourceUid the unique id of the data source containing the item. It is used to get
     * the data provider associated to the data source, and pass it to for the variable creation
     * @param productItem the item to load
     */
    void loadProductItem(const QUuid &dataSourceUid, const DataSourceItem &productItem) noexcept;

    QByteArray mimeDataForProductsData(const QVariantList &productsData) const;
    QVariantList productsDataForMimeData(const QByteArray &mimeData) const;

public slots:
    /// Manage init/end of the controller
    void initialize();
    void finalize();

signals:
    /// Signal emitted when a structure has been set for a data source
    void dataSourceItemSet(DataSourceItem *dataSourceItem);

    /**
     * Signal emitted when a variable creation is asked for a product
     * @param variableName the name of the variable
     * @param variableMetadata the metadata of the variable
     * @param variableProvider the provider that will be used to retrieve the data of the variable
     * (can be null)
     */
    void variableCreationRequested(const QString &variableName,
                                   const QVariantHash &variableMetadata,
                                   std::shared_ptr<IDataProvider> variableProvider);

private:
    void waitForFinish();

    class DataSourceControllerPrivate;
    spimpl::unique_impl_ptr<DataSourceControllerPrivate> impl;
};

#endif // SCIQLOP_DATASOURCECONTROLLER_H
