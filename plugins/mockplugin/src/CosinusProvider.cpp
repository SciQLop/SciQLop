#include "CosinusProvider.h"
#include "MockDefs.h"

#include <Data/DataProviderParameters.h>
#include <Data/ScalarTimeSerie.h>
#include <Data/SpectrogramTimeSerie.h>
#include <Data/VectorTimeSerie.h>

#include <cmath>
#include <set>

#include <QFuture>
#include <QThread>
#include <QtConcurrent/QtConcurrent>


namespace
{

/// Number of bands generated for a spectrogram
const auto SPECTROGRAM_NUMBER_BANDS = 30;

/// Bands for which to generate NaN values for a spectrogram
const auto SPECTROGRAM_NAN_BANDS = std::set<int> { 1, 3, 10, 20 };

/// Bands for which to generate zeros for a spectrogram
const auto SPECTROGRAM_ZERO_BANDS = std::set<int> { 2, 15, 19, 29 };


} // namespace

std::shared_ptr<IDataProvider> CosinusProvider::clone() const
{
    // No copy is made in clone
    return std::make_shared<CosinusProvider>();
}

TimeSeries::ITimeSerie* CosinusProvider::_generate(
    const DateTimeRange& range, const QVariantHash& metaData)
{
    // Retrieves cosinus type
    auto typeVariant = metaData.value(COSINUS_TYPE_KEY, COSINUS_TYPE_DEFAULT_VALUE);
    auto freqVariant = metaData.value(COSINUS_FREQUENCY_KEY, COSINUS_FREQUENCY_DEFAULT_VALUE);
    const auto fs = 200.;
    double freq = freqVariant.toDouble();
    double start = std::ceil(range.m_TStart * freq);
    double end = std::floor(range.m_TEnd * freq);
    if (end < start)
    {
        std::swap(start, end);
    }
    std::size_t dataCount = static_cast<std::size_t>(end - start + 1);
    if (typeVariant.toString() == QStringLiteral("scalar"))
    {
        auto ts = new ScalarTimeSerie(dataCount);
        std::generate(
            std::begin(*ts), std::end(*ts), [range, freq, fs, dt = 1. / freq, i = 0.]() mutable {
                auto t = range.m_TStart + i * dt;
                i++;
                return std::pair<double, double> { t, std::cos(2 * 3.14 * freq / fs * t) };
            });
        return ts;
    }
    if (typeVariant.toString() == QStringLiteral("vector"))
    {
        auto ts = new VectorTimeSerie(dataCount);
        std::generate(
            std::begin(*ts), std::end(*ts), [range, freq, fs, dt = 1. / freq, i = 0.]() mutable {
                auto t = range.m_TStart + i * dt;
                i++;
                return std::pair<double, VectorTimeSerie::raw_value_type> { t,
                    { std::cos(2 * 3.14 * freq / fs * t), std::sin(2 * 3.14 * freq / fs * t),
                        std::cos(2 * 3.14 * freq / fs * t) * std::sin(2 * 3.14 * freq / fs * t) } };
            });
        return ts;
    }
    if (typeVariant.toString() == QStringLiteral("spectrogram"))
    {
        return nullptr;
    }
    return nullptr;
}

TimeSeries::ITimeSerie* CosinusProvider::getData(const DataProviderParameters& parameters)
{
    return _generate(parameters.m_Range, parameters.m_Data);
}
