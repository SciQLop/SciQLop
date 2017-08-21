#ifndef SCIQLOP_VISUALIZATIONGRAPHHELPER_H
#define SCIQLOP_VISUALIZATIONGRAPHHELPER_H

#include "Visualization/VisualizationDefs.h"

#include <Data/SqpRange.h>

#include <QLoggingCategory>
#include <QVector>

#include <memory>

Q_DECLARE_LOGGING_CATEGORY(LOG_VisualizationGraphHelper)

class IDataSeries;
class QCPAbstractPlottable;
class QCustomPlot;
class Variable;

/**
 * @brief The VisualizationGraphHelper class aims to create the QCustomPlot components relative to a
 * variable, depending on the data series of this variable
 */
struct VisualizationGraphHelper {
    /**
     * Creates (if possible) the QCustomPlot components relative to the variable passed in
     * parameter, and adds these to the plot passed in parameter.
     * @param variable the variable for which to create the components
     * @param plot the plot in which to add the created components. It takes ownership of these
     * components.
     * @return the list of the components created
     */
    static PlottablesMap create(std::shared_ptr<Variable> variable, QCustomPlot &plot) noexcept;

    static void updateData(PlottablesMap &plottables, std::shared_ptr<IDataSeries> dataSeries,
                           const SqpRange &dateTime);
};

#endif // SCIQLOP_VISUALIZATIONGRAPHHELPER_H
