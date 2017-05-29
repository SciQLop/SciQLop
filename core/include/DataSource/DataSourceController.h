#ifndef SCIQLOP_DATASOURCECONTROLLER_H
#define SCIQLOP_DATASOURCECONTROLLER_H

#include "DataSourceController.h"

#include <QLoggingCategory>
#include <QObject>

#include <Common/spimpl.h>

Q_DECLARE_LOGGING_CATEGORY(LOG_DataSourceController)

/**
 * @brief The DataSourceController class aims to make the link between SciQlop
 * and its plugins. This is the intermediate class that SciQlop have to use
 * in the way to connect a data source. Please first use load method to intialize
 * a plugin specified by its metadata name (JSON plugin source) then others specifics
 * method will ba able to access it.
 * You can load a data source driver plugin then create a data source.
 */
class DataSourceController : public QObject {
    Q_OBJECT
public:
    explicit DataSourceController(QObject *parent = 0);
    virtual ~DataSourceController();

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
