#ifndef SCIQLOP_DATASOURCECONTROLLER_H
#define SCIQLOP_DATASOURCECONTROLLER_H

#include <QLoggingCategory>
#include <QObject>
#include <QUuid>

#include <Common/spimpl.h>

Q_DECLARE_LOGGING_CATEGORY(LOG_DataSourceController)

/**
 * @brief The DataSourceController class aims to make the link between SciQlop and its plugins. This
 * is the intermediate class that SciQlop has to use in the way to connect a data source. Please
 * first use register method to initialize a plugin specified by its metadata name (JSON plugin
 * source) then others specifics method will be able to access it. You can load a data source driver
 * plugin then create a data source.
 */
class DataSourceController : public QObject {
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

public slots:
    /// Manage init/end of the controller
    void initialize();
    void finalize();

private:
    void waitForFinish();

    class DataSourceControllerPrivate;
    spimpl::unique_impl_ptr<DataSourceControllerPrivate> impl;
};

#endif // SCIQLOP_DATASOURCECONTROLLER_H
