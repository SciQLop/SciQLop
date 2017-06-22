#ifndef SCIQLOP_IVISUALIZATIONWIDGET_H
#define SCIQLOP_IVISUALIZATIONWIDGET_H


#include <QString>
#include <memory>

class IVisualizationWidgetVisitor;

/**
 * @brief The IVisualizationWidget handles the visualization widget.
 */
class IVisualizationWidget {

public:
    virtual ~IVisualizationWidget() = default;

    /// Initializes the plugin
    virtual void accept(IVisualizationWidgetVisitor *visitor) = 0;
    virtual void close() = 0;
    virtual QString name() const = 0;
};


#endif // SCIQLOP_IVISUALIZATIONWIDGET_H
