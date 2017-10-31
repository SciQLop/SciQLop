#ifndef SCIQLOP_DATASERIESBUILDERS_H
#define SCIQLOP_DATASERIESBUILDERS_H

#include <memory>
#include <vector>

class ScalarSeries;
class SpectrogramSeries;
class VectorSeries;

/**
 * @brief The ScalarBuilder class aims to facilitate the creation of a ScalarSeries for unit tests
 * @sa ScalarSeries
 */
class ScalarBuilder {
public:
    /// Sets x-axis data of the series
    ScalarBuilder & setX(std::vector<double> xData);
    /// Sets values data of the series
    ScalarBuilder & setValues(std::vector<double> valuesData);
    /// Creates the series
    std::shared_ptr<ScalarSeries> build();

private:
    std::vector<double> m_XAxisData{};
    std::vector<double> m_ValuesData{};
};

/**
 * @brief The SpectrogramBuilder class aims to facilitate the creation of a SpectrogramSeries for unit tests
 * @sa SpectrogramSeries
 */
class SpectrogramBuilder {
public:
    /// Sets x-axis data of the series
    SpectrogramBuilder & setX(std::vector<double> xData);
    /// Sets y-axis data of the series
    SpectrogramBuilder & setY(std::vector<double> yData);
    /// Sets values data of the series
    SpectrogramBuilder & setValues(std::vector<double> valuesData);
    /// Creates the series
    std::shared_ptr<SpectrogramSeries> build();

private:
    std::vector<double> m_XAxisData{};
    std::vector<double> m_YAxisData{};
    std::vector<double> m_ValuesData{};
};

/**
 * @brief The VectorBuilder class aims to facilitate the creation of a VectorSeries for unit tests
 * @sa VectorSeries
 */
class VectorBuilder {
public:
    /// Sets x-axis data of the series
    VectorBuilder & setX(std::vector<double> xData);
    /// Sets x-values data of the series
    VectorBuilder & setXValues(std::vector<double> xValuesData);
    /// Sets y-values data of the series
    VectorBuilder & setYValues(std::vector<double> yValuesData);
    /// Sets z-values data of the series
    VectorBuilder & setZValues(std::vector<double> zValuesData);
    /// Creates the series
    std::shared_ptr<VectorSeries> build();

private:
    std::vector<double> m_XAxisData{};
    std::vector<double> m_XValuesData{};
    std::vector<double> m_YValuesData{};
    std::vector<double> m_ZValuesData{};
};

#endif // SCIQLOP_DATASERIESBUILDERS_H
