#ifndef SCIQLOP_VISUALIZATIONCONTROLLER_H
#define SCIQLOP_VISUALIZATIONCONTROLLER_H

#include <QLoggingCategory>
#include <QObject>
#include <QUuid>

#include <Common/spimpl.h>

Q_DECLARE_LOGGING_CATEGORY(LOG_VisualizationController)

class DataSourceItem;

/**
 * @brief The VisualizationController class aims to make the link between SciQlop and its plugins.
 * This is the intermediate class that SciQlop has to use in the way to connect a data source.
 * Please first use register method to initialize a plugin specified by its metadata name (JSON
 * plugin source) then others specifics method will be able to access it. You can load a data source
 * driver plugin then create a data source.
 */
class VisualizationController : public QObject {
    Q_OBJECT
public:
    explicit VisualizationController(QObject *parent = 0);
    virtual ~VisualizationController();

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
