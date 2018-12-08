#include "Visualization/AxisRenderingUtils.h"

#include <Data/ScalarSeries.h>
#include <Data/SpectrogramSeries.h>
#include <Data/VectorSeries.h>

#include <Variable/Variable.h>

#include <Visualization/SqpColorScale.h>
#include <Visualization/qcustomplot.h>

Q_LOGGING_CATEGORY(LOG_AxisRenderingUtils, "AxisRenderingUtils")

namespace {

/// Format for datetimes on a axis
const auto DATETIME_TICKER_FORMAT = QStringLiteral("yyyy/MM/dd \nhh:mm:ss");

const auto NUMBER_FORMAT = 'g';
const auto NUMBER_PRECISION = 9;

/// Generates the appropriate ticker for an axis, depending on whether the axis displays time or
/// non-time data
QSharedPointer<QCPAxisTicker> axisTicker(bool isTimeAxis, QCPAxis::ScaleType scaleType)
{
    if (isTimeAxis) {
        auto dateTicker = QSharedPointer<QCPAxisTickerDateTime>::create();
        dateTicker->setDateTimeFormat(DATETIME_TICKER_FORMAT);
        dateTicker->setDateTimeSpec(Qt::UTC);

        return dateTicker;
    }
    else if (scaleType == QCPAxis::stLogarithmic) {
        return QSharedPointer<QCPAxisTickerLog>::create();
    }
    else {
        // default ticker
        return QSharedPointer<QCPAxisTicker>::create();
    }
}

/**
 * Sets properties of the axis passed as parameter
 * @param axis the axis to set
 * @param unit the unit to set for the axis
 * @param scaleType the scale type to set for the axis
 */
void setAxisProperties(QCPAxis &axis, const Unit &unit,
                       QCPAxis::ScaleType scaleType = QCPAxis::stLinear)
{
    // label (unit name)
    axis.setLabel(unit.m_Name);

    // scale type
    axis.setScaleType(scaleType);
    if (scaleType == QCPAxis::stLogarithmic) {
        // Scientific notation
        axis.setNumberPrecision(0);
        axis.setNumberFormat("eb");
    }

    // ticker (depending on the type of unit)
    axis.setTicker(axisTicker(unit.m_TimeUnit, scaleType));
}

/**
 * Delegate used to set axes properties
 */
template <typename T, typename Enabled = void>
struct AxisSetter {
    static void setProperties(QCustomPlot &, SqpColorScale &)
    {
        // Default implementation does nothing
        qCCritical(LOG_AxisRenderingUtils()) << "Can't set axis properties: unmanaged type of data";
    }

    static void setUnits(T &, QCustomPlot &, SqpColorScale &)
    {
        // Default implementation does nothing
        qCCritical(LOG_AxisRenderingUtils()) << "Can't set axis units: unmanaged type of data";
    }
};

/**
 * Specialization of AxisSetter for scalars and vectors
 * @sa ScalarSeries
 * @sa VectorSeries
 */
template <typename T>
struct AxisSetter<T, typename std::enable_if_t<std::is_base_of<ScalarSeries, T>::value
                                               or std::is_base_of<VectorSeries, T>::value> > {
    static void setProperties(QCustomPlot &, SqpColorScale &)
    {
        // Nothing to do
    }

    static void setUnits(T &dataSeries, QCustomPlot &plot, SqpColorScale &)
    {
        dataSeries.lockRead();
        auto xAxisUnit = dataSeries.xAxisUnit();
        auto valuesUnit = dataSeries.valuesUnit();
        dataSeries.unlock();

//        setAxisProperties(*plot.xAxis, xAxisUnit);
        // This is cheating but it's ok ;)
        setAxisProperties(*plot.xAxis, Unit{"s", true});
        setAxisProperties(*plot.yAxis, valuesUnit);
    }
};

/**
 * Specialization of AxisSetter for spectrograms
 * @sa SpectrogramSeries
 */
template <typename T>
struct AxisSetter<T, typename std::enable_if_t<std::is_base_of<SpectrogramSeries, T>::value> > {
    static void setProperties(QCustomPlot &plot, SqpColorScale &colorScale)
    {
        // Displays color scale in plot
        plot.plotLayout()->insertRow(0);
        plot.plotLayout()->addElement(0, 0, colorScale.m_Scale);
        colorScale.m_Scale->setType(QCPAxis::atTop);
        colorScale.m_Scale->setMinimumMargins(QMargins{0, 0, 0, 0});

        // Aligns color scale with axes
        auto marginGroups = plot.axisRect()->marginGroups();
        for (auto it = marginGroups.begin(), end = marginGroups.end(); it != end; ++it) {
            colorScale.m_Scale->setMarginGroup(it.key(), it.value());
        }

        // Set color scale properties
        colorScale.m_AutomaticThreshold = true;
    }

    static void setUnits(T &dataSeries, QCustomPlot &plot, SqpColorScale &colorScale)
    {
        dataSeries.lockRead();
        auto xAxisUnit = dataSeries.xAxisUnit();
        auto yAxisUnit = dataSeries.yAxisUnit();
        auto valuesUnit = dataSeries.valuesUnit();
        dataSeries.unlock();

        //setAxisProperties(*plot.xAxis, xAxisUnit);
        // This is cheating but it's ok ;)
        setAxisProperties(*plot.xAxis, Unit{"s", true});
        setAxisProperties(*plot.yAxis, yAxisUnit, QCPAxis::stLogarithmic);
        setAxisProperties(*colorScale.m_Scale->axis(), valuesUnit, QCPAxis::stLogarithmic);
    }
};

/**
 * Default implementation of IAxisHelper, which takes data series to set axes properties
 * @tparam T the data series' type
 */
template <typename T>
struct AxisHelper : public IAxisHelper {
    explicit AxisHelper(std::shared_ptr<T> dataSeries) : m_DataSeries{dataSeries} {}

    void setProperties(QCustomPlot &plot, SqpColorScale &colorScale) override
    {
        AxisSetter<T>::setProperties(plot, colorScale);
    }

    void setUnits(QCustomPlot &plot, SqpColorScale &colorScale) override
    {
        if (m_DataSeries) {
            AxisSetter<T>::setUnits(*m_DataSeries, plot, colorScale);
        }
        else {
            qCCritical(LOG_AxisRenderingUtils()) << "Can't set units: inconsistency between the "
                                                    "type of data series and the type supposed";
        }
    }

    std::shared_ptr<T> m_DataSeries;
};

} // namespace

QString formatValue(double value, const QCPAxis &axis)
{
    // If the axis is a time axis, formats the value as a date
    if (auto axisTicker = qSharedPointerDynamicCast<QCPAxisTickerDateTime>(axis.ticker())) {
        return DateUtils::dateTime(value, axisTicker->dateTimeSpec()).toString(DATETIME_FORMAT);
    }
    else {
        return QString::number(value, NUMBER_FORMAT, NUMBER_PRECISION);
    }
}

std::unique_ptr<IAxisHelper> IAxisHelperFactory::create(const Variable &variable) noexcept
{
    switch (variable.type()) {
        case DataSeriesType::SCALAR:
            return std::make_unique<AxisHelper<ScalarSeries> >(
                std::dynamic_pointer_cast<ScalarSeries>(variable.dataSeries()));
        case DataSeriesType::SPECTROGRAM:
            return std::make_unique<AxisHelper<SpectrogramSeries> >(
                std::dynamic_pointer_cast<SpectrogramSeries>(variable.dataSeries()));
        case DataSeriesType::VECTOR:
            return std::make_unique<AxisHelper<VectorSeries> >(
                std::dynamic_pointer_cast<VectorSeries>(variable.dataSeries()));
        default:
            // Creates default helper
            break;
    }

    return std::make_unique<AxisHelper<IDataSeries> >(nullptr);
}
