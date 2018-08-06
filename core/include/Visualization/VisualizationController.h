#ifndef SCIQLOP_VISUALIZATIONCONTROLLER_H
#define SCIQLOP_VISUALIZATIONCONTROLLER_H

#include "CoreGlobal.h"

#include <Data/SqpRange.h>

#include <QLoggingCategory>
#include <QObject>
#include <QUuid>

#include <Common/spimpl.h>

Q_DECLARE_LOGGING_CATEGORY(LOG_VisualizationController)

class DataSourceItem;
class Variable;

/**
 * @brief The VisualizationController class aims to make the link between SciQlop and its plugins.
 * This is the intermediate class that SciQlop has to use in the way to connect a data source.
 * Please first use register method to initialize a plugin specified by its metadata name (JSON
 * plugin source) then others specifics method will be able to access it. You can load a data source
 * driver plugin then create a data source.
 */
class SCIQLOP_CORE_EXPORT VisualizationController : public QObject {
    Q_OBJECT
public:
    explicit VisualizationController(QObject *parent = 0);
    virtual ~VisualizationController();

signals:
    /// Signal emitted when a variable is about to be deleted from SciQlop
    void variableAboutToBeDeleted(std::shared_ptr<Variable> variable);

    /// Signal emitted when a data acquisition is requested on a range for a variable
    void rangeChanged(std::shared_ptr<Variable> variable, const DateTimeRange &range);

public slots:
    /// Manage init/end of the controller
    void initialize();
    void finalize();

private:
    void waitForFinish();

    class VisualizationControllerPrivate;
    spimpl::unique_impl_ptr<VisualizationControllerPrivate> impl;
};

#endif // SCIQLOP_VISUALIZATIONCONTROLLER_H
