#include "DataSeriesBuilders.h"

#include <Data/ScalarSeries.h>
#include <Data/SpectrogramSeries.h>
#include <Data/VectorSeries.h>
#include <Data/Unit.h>

// ///////////// //
// ScalarBuilder //
// ///////////// //

ScalarBuilder &ScalarBuilder::setX(std::vector<double> xData)
{
    m_XAxisData = std::move(xData);
    return *this;
}

ScalarBuilder &ScalarBuilder::setValues(std::vector<double> valuesData)
{
    m_ValuesData =std::move(valuesData);
    return *this;
}

std::shared_ptr<ScalarSeries> ScalarBuilder::build()
{
    return std::make_shared<ScalarSeries>(std::move(m_XAxisData), std::move(m_ValuesData), Unit{},
                                          Unit{});
}

// ////////////////// //
// SpectrogramBuilder //
// ////////////////// //

SpectrogramBuilder &SpectrogramBuilder::setX(std::vector<double> xData)
{
    m_XAxisData = std::move(xData);
    return *this;
}

SpectrogramBuilder &SpectrogramBuilder::setY(std::vector<double> yData)
{
    m_YAxisData =std::move(yData);
    return *this;
}

SpectrogramBuilder &SpectrogramBuilder::setValues(std::vector<double> valuesData)
{
    m_ValuesData =std::move(valuesData);
    return *this;
}

std::shared_ptr<SpectrogramSeries> SpectrogramBuilder::build()
{
    return std::make_shared<SpectrogramSeries>(std::move(m_XAxisData), std::move(m_YAxisData), std::move(m_ValuesData), Unit{},
                                          Unit{}, Unit{});
}

// ///////////// //
// VectorBuilder //
// ///////////// //

VectorBuilder &VectorBuilder::setX(std::vector<double> xData)
{
    m_XAxisData = std::move(xData);
    return *this;
}

VectorBuilder &VectorBuilder::setXValues(std::vector<double> xValuesData)
{
    m_XValuesData =std::move(xValuesData);
    return *this;
}

VectorBuilder &VectorBuilder::setYValues(std::vector<double> yValuesData)
{
    m_YValuesData =std::move(yValuesData);
    return *this;
}

VectorBuilder &VectorBuilder::setZValues(std::vector<double> zValuesData)
{
    m_ZValuesData =std::move(zValuesData);
    return *this;
}

std::shared_ptr<VectorSeries> VectorBuilder::build()
{
    return std::make_shared<VectorSeries>(std::move(m_XAxisData), std::move(m_XValuesData), std::move(m_YValuesData), std::move(m_ZValuesData), Unit{},
                                          Unit{});
}
