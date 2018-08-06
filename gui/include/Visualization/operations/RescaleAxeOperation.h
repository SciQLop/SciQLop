#ifndef SCIQLOP_RESCALEAXEOPERATION_H
#define SCIQLOP_RESCALEAXEOPERATION_H

#include "Visualization/IVisualizationWidgetVisitor.h"
#include <Data/SqpRange.h>

#include <Common/spimpl.h>

#include <QLoggingCategory>

#include <memory>

class Variable;

Q_DECLARE_LOGGING_CATEGORY(LOG_RescaleAxeOperation)

/**
 * @brief The RescaleAxeOperation class defines an operation that traverses all of visualization
 * widgets to remove a variable if they contain it
 */
class RescaleAxeOperation : public IVisualizationWidgetVisitor {
public:
    /**
     * Ctor
     * @param variable the variable to remove from widgets
     */
    explicit RescaleAxeOperation(std::shared_ptr<Variable> variable, const DateTimeRange &range);

    void visitEnter(VisualizationWidget *widget) override final;
    void visitLeave(VisualizationWidget *widget) override final;
    void visitEnter(VisualizationTabWidget *tabWidget) override final;
    void visitLeave(VisualizationTabWidget *tabWidget) override final;
    void visitEnter(VisualizationZoneWidget *zoneWidget) override final;
    void visitLeave(VisualizationZoneWidget *zoneWidget) override final;
    void visit(VisualizationGraphWidget *graphWidget) override final;

private:
    class RescaleAxeOperationPrivate;
    spimpl::unique_impl_ptr<RescaleAxeOperationPrivate> impl;
};

#endif // SCIQLOP_RESCALEAXEOPERATION_H
