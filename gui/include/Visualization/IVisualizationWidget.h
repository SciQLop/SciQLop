#ifndef SCIQLOP_IVISUALIZATIONWIDGET_H
#define SCIQLOP_IVISUALIZATIONWIDGET_H

#include "Visualization/IVisualizationWidgetVisitor.h"

#include <QString>
#include <memory>

/**
 * @brief The IVisualizationWidget handles the visualization widget.
 */
class IVisualizationWidget {

public:
    virtual ~IVisualizationWidget() = default;

    /// Initializes the plugin
    virtual void accept(IVisualizationWidget *visitor) = 0;
    virtual void close() = 0;
    virtual QString name() = 0;
};


#endif // SCIQLOP_IVISUALIZATIONWIDGET_H
