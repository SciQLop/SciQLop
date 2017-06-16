#include "Visualization/GraphPlottablesFactory.h"
#include "Visualization/qcustomplot.h"

#include <Variable/Variable.h>

Q_LOGGING_CATEGORY(LOG_GraphPlottablesFactory, "GraphPlottablesFactory")

QVector<QCPAbstractPlottable *> GraphPlottablesFactory::create(const Variable *variable,
                                                               QCustomPlot &plot) noexcept
{
    auto result = QVector<QCPAbstractPlottable *>{};

    if (variable) {
        /// @todo ALX
    }
    else {
        qCDebug(LOG_GraphPlottablesFactory())
            << QObject::tr("Can't create graph plottables : the variable is null");
    }

    return result;
}
