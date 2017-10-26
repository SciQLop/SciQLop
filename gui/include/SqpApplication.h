#ifndef SCIQLOP_SQPAPPLICATION_H
#define SCIQLOP_SQPAPPLICATION_H

#include "SqpApplication.h"

#include <QApplication>
#include <QLoggingCategory>

#include <Common/spimpl.h>

Q_DECLARE_LOGGING_CATEGORY(LOG_SqpApplication)

#if defined(sqpApp)
#undef sqpApp
#endif
#define sqpApp (static_cast<SqpApplication *>(QCoreApplication::instance()))

class DataSourceController;
class NetworkController;
class TimeController;
class VariableController;
class VisualizationController;
class DragDropHelper;

/**
 * @brief The SqpApplication class aims to make the link between SciQlop
 * and its plugins. This is the intermediate class that SciQlop has to use
 * in the way to connect a data source. Please first use load method to initialize
 * a plugin specified by its metadata name (JSON plugin source) then others specifics
 * method will be able to access it.
 * You can load a data source driver plugin then create a data source.
 */

class SqpApplication : public QApplication {
    Q_OBJECT
public:
    explicit SqpApplication(int &argc, char **argv);
    virtual ~SqpApplication();
    void initialize();

    /// Accessors for the differents sciqlop controllers
    DataSourceController &dataSourceController() noexcept;
    NetworkController &networkController() noexcept;
    TimeController &timeController() noexcept;
    VariableController &variableController() noexcept;
    VisualizationController &visualizationController() noexcept;

    /// Accessors for the differents sciqlop helpers
    DragDropHelper &dragDropHelper() noexcept;

private:
    class SqpApplicationPrivate;
    spimpl::unique_impl_ptr<SqpApplicationPrivate> impl;
};

#endif // SCIQLOP_SQPAPPLICATION_H
