#include "AmdaResultParserHelper.h"

#include <Common/DateUtils.h>
#include <Common/SortUtils.h>

#include <Data/ScalarSeries.h>
#include <Data/SpectrogramSeries.h>
#include <Data/Unit.h>
#include <Data/VectorSeries.h>

#include <QtCore/QDateTime>
#include <QtCore/QRegularExpression>

#include <functional>

Q_LOGGING_CATEGORY(LOG_AmdaResultParserHelper, "AmdaResultParserHelper")

namespace {

// ///////// //
// Constants //
// ///////// //

/// Separator between values in a result line
const auto RESULT_LINE_SEPARATOR = QRegularExpression{QStringLiteral("\\s+")};

/// Format for dates in result files
const auto DATE_FORMAT = QStringLiteral("yyyy-MM-ddThh:mm:ss.zzz");

// /////// //
// Methods //
// /////// //

/**
 * Checks that the properties contain a specific unit and that this unit is valid
 * @param properties the properties map in which to search unit
 * @param key the key to search for the unit in the properties
 * @param errorMessage the error message to log in case the unit is invalid
 * @return true if the unit is valid, false it it's invalid or was not found in the properties
 */
bool checkUnit(const Properties &properties, const QString &key, const QString &errorMessage)
{
    auto unit = properties.value(key).value<Unit>();
    if (unit.m_Name.isEmpty()) {
        qCWarning(LOG_AmdaResultParserHelper()) << errorMessage;
        return false;
    }

    return true;
}

QDateTime dateTimeFromString(const QString &stringDate) noexcept
{
#if QT_VERSION >= QT_VERSION_CHECK(5, 8, 0)
    return QDateTime::fromString(stringDate, Qt::ISODateWithMs);
#else
    return QDateTime::fromString(stringDate, DATE_FORMAT);
#endif
}

/// Converts a string date to a double date
/// @return a double that represents the date in seconds, NaN if the string date can't be converted
double doubleDate(const QString &stringDate) noexcept
{
    // Format: yyyy-MM-ddThh:mm:ss.zzz
    auto dateTime = dateTimeFromString(stringDate);
    dateTime.setTimeSpec(Qt::UTC);
    return dateTime.isValid() ? DateUtils::secondsSinceEpoch(dateTime)
                              : std::numeric_limits<double>::quiet_NaN();
}

/**
 * Reads a line from the AMDA file and tries to extract a x-axis data and value data from it
 * @param xAxisData the vector in which to store the x-axis data extracted
 * @param valuesData the vector in which to store the value extracted
 * @param line the line to read to extract the property
 * @param valuesIndexes indexes of insertion of read values. For example, if the line contains three
 * columns of values, and valuesIndexes are {2, 0, 1}, the value of the third column will be read
 * and inserted first, then the value of the first column, and finally the value of the second
 * column.
 * @param fillValue value that tags an invalid data. For example, if fillValue is -1 and a read
 * value is -1, then this value is considered as invalid and converted to NaN
 */
void tryReadResult(std::vector<double> &xAxisData, std::vector<double> &valuesData,
                   const QString &line, const std::vector<int> &valuesIndexes,
                   double fillValue = std::numeric_limits<double>::quiet_NaN())
{
    auto lineData = line.split(RESULT_LINE_SEPARATOR, QString::SkipEmptyParts);

    // Checks that the line contains expected number of values + x-axis value
    if (static_cast<size_t>(lineData.size()) == valuesIndexes.size() + 1) {
        // X : the data is converted from date to double (in secs)
        auto x = doubleDate(lineData.at(0));

        // Adds result only if x is valid. Then, if value is invalid, it is set to NaN
        if (!std::isnan(x)) {
            xAxisData.push_back(x);

            // Values
            for (auto valueIndex : valuesIndexes) {
                bool valueOk;
                // we use valueIndex + 1 to skip column 0 (x-axis value)
                auto value = lineData.at(valueIndex + 1).toDouble(&valueOk);

                if (!valueOk) {
                    qCWarning(LOG_AmdaResultParserHelper())
                        << QObject::tr(
                               "Value from (line %1, column %2) is invalid and will be "
                               "converted to NaN")
                               .arg(line, valueIndex);
                    value = std::numeric_limits<double>::quiet_NaN();
                }

                // Handles fill value
                if (!std::isnan(fillValue) && !std::isnan(value) && fillValue == value) {
                    value = std::numeric_limits<double>::quiet_NaN();
                }

                valuesData.push_back(value);
            }
        }
        else {
            qCWarning(LOG_AmdaResultParserHelper())
                << QObject::tr("Can't retrieve results from line %1: x is invalid").arg(line);
        }
    }
    else {
        qCWarning(LOG_AmdaResultParserHelper())
            << QObject::tr("Can't retrieve results from line %1: invalid line").arg(line);
    }
}

/**
 * Reads a line from the AMDA file and tries to extract a property from it
 * @param properties the properties map in which to put the property extracted from the line
 * @param key the key to which the property is added in the properties map
 * @param line the line to read to extract the property
 * @param regex the expected regex to extract the property. If the line matches this regex, the
 * property is generated
 * @param fun the function used to generate the property
 * @return true if the property could be generated, false if the line does not match the regex, or
 * if a property has already been generated for the key
 */
template <typename GeneratePropertyFun>
bool tryReadProperty(Properties &properties, const QString &key, const QString &line,
                     const QRegularExpression &regex, GeneratePropertyFun fun)
{
    if (properties.contains(key)) {
        return false;
    }

    auto match = regex.match(line);
    if (match.hasMatch()) {
        properties.insert(key, fun(match));
    }

    return match.hasMatch();
}

/**
 * Reads a line from the AMDA file and tries to extract a double from it
 * @sa tryReadProperty()
 */
bool tryReadDouble(Properties &properties, const QString &key, const QString &line,
                   const QRegularExpression &regex)
{
    return tryReadProperty(properties, key, line, regex, [](const auto &match) {
        bool ok;

        // If the value can't be converted to double, it is set to NaN
        auto doubleValue = match.captured(1).toDouble(&ok);
        if (!ok) {
            doubleValue = std::numeric_limits<double>::quiet_NaN();
        }

        return QVariant::fromValue(doubleValue);
    });
}

/**
 * Reads a line from the AMDA file and tries to extract a vector of doubles from it
 * @param sep the separator of double values in the line
 * @sa tryReadProperty()
 */
bool tryReadDoubles(Properties &properties, const QString &key, const QString &line,
                    const QRegularExpression &regex, const QString &sep = QStringLiteral(","))
{
    return tryReadProperty(properties, key, line, regex, [sep](const auto &match) {
        std::vector<double> doubleValues{};

        // If the value can't be converted to double, it is set to NaN
        auto values = match.captured(1).split(sep);
        for (auto value : values) {
            bool ok;

            auto doubleValue = value.toDouble(&ok);
            if (!ok) {
                doubleValue = std::numeric_limits<double>::quiet_NaN();
            }

            doubleValues.push_back(doubleValue);
        }

        return QVariant::fromValue(doubleValues);
    });
}

/**
 * Reads a line from the AMDA file and tries to extract a unit from it
 * @sa tryReadProperty()
 */
bool tryReadUnit(Properties &properties, const QString &key, const QString &line,
                 const QRegularExpression &regex, bool timeUnit = false)
{
    return tryReadProperty(properties, key, line, regex, [timeUnit](const auto &match) {
        return QVariant::fromValue(Unit{match.captured(1), timeUnit});
    });
}

} // namespace

// ////////////////// //
// ScalarParserHelper //
// ////////////////// //

bool ScalarParserHelper::checkProperties()
{
    return checkUnit(m_Properties, X_AXIS_UNIT_PROPERTY,
                     QObject::tr("The x-axis unit could not be found in the file"));
}

std::shared_ptr<IDataSeries> ScalarParserHelper::createSeries()
{
    return std::make_shared<ScalarSeries>(std::move(m_XAxisData), std::move(m_ValuesData),
                                          m_Properties.value(X_AXIS_UNIT_PROPERTY).value<Unit>(),
                                          m_Properties.value(VALUES_UNIT_PROPERTY).value<Unit>());
}

void ScalarParserHelper::readPropertyLine(const QString &line)
{
    tryReadUnit(m_Properties, X_AXIS_UNIT_PROPERTY, line, DEFAULT_X_AXIS_UNIT_REGEX, true);
}

void ScalarParserHelper::readResultLine(const QString &line)
{
    tryReadResult(m_XAxisData, m_ValuesData, line, valuesIndexes());
}

std::vector<int> ScalarParserHelper::valuesIndexes() const
{
    // Only one value to read
    static auto result = std::vector<int>{0};
    return result;
}

// /////////////////////// //
// SpectrogramParserHelper //
// /////////////////////// //

bool SpectrogramParserHelper::checkProperties()
{
    // Generates y-axis data from bands extracted (take the middle of the intervals)
    auto minBands = m_Properties.value(MIN_BANDS_PROPERTY).value<std::vector<double> >();
    auto maxBands = m_Properties.value(MAX_BANDS_PROPERTY).value<std::vector<double> >();

    if (minBands.size() != maxBands.size()) {
        qCWarning(LOG_AmdaResultParserHelper()) << QObject::tr(
            "Can't generate y-axis data from bands extracted: bands intervals are invalid");
        return false;
    }

    std::transform(
        minBands.begin(), minBands.end(), maxBands.begin(), std::back_inserter(m_YAxisData),
        [](const auto &minValue, const auto &maxValue) { return (minValue + maxValue) / 2.; });

    // Generates values indexes, i.e. the order in which each value will be retrieved (in ascending
    // order of the associated bands)
    m_ValuesIndexes = SortUtils::sortPermutation(m_YAxisData, std::less<double>());

    // Sorts y-axis data accoding to the ascending order
    m_YAxisData = SortUtils::sort(m_YAxisData, 1, m_ValuesIndexes);

    // Sets fill value
    m_FillValue = m_Properties.value(FILL_VALUE_PROPERTY).value<double>();

    /// @todo: handle min/max samplings?

    return true;
}

std::shared_ptr<IDataSeries> SpectrogramParserHelper::createSeries()
{
    return std::make_shared<SpectrogramSeries>(
        std::move(m_XAxisData), std::move(m_YAxisData), std::move(m_ValuesData),
        Unit{"t", true}, // x-axis unit is always a time unit
        m_Properties.value(Y_AXIS_UNIT_PROPERTY).value<Unit>(),
        m_Properties.value(VALUES_UNIT_PROPERTY).value<Unit>());
}

void SpectrogramParserHelper::readPropertyLine(const QString &line)
{
    // Set of functions to test on the line to generate a property. If a function is valid (i.e. a
    // property has been generated for the line), the line is treated as processed and the other
    // functions are not called
    std::vector<std::function<bool()> > functions{
        // values unit
        [&] {
            return tryReadUnit(m_Properties, VALUES_UNIT_PROPERTY, line,
                               SPECTROGRAM_VALUES_UNIT_REGEX);
        },
        // y-axis unit
        [&] {
            return tryReadUnit(m_Properties, Y_AXIS_UNIT_PROPERTY, line,
                               SPECTROGRAM_Y_AXIS_UNIT_REGEX);
        },
        // min sampling
        [&] {
            return tryReadDouble(m_Properties, MIN_SAMPLING_PROPERTY, line,
                                 SPECTROGRAM_MIN_SAMPLING_REGEX);
        },
        // max sampling
        [&] {
            return tryReadDouble(m_Properties, MAX_SAMPLING_PROPERTY, line,
                                 SPECTROGRAM_MAX_SAMPLING_REGEX);
        },
        // fill value
        [&] {
            return tryReadDouble(m_Properties, FILL_VALUE_PROPERTY, line,
                                 SPECTROGRAM_FILL_VALUE_REGEX);
        },
        // min bounds of each band
        [&] {
            return tryReadDoubles(m_Properties, MIN_BANDS_PROPERTY, line,
                                  SPECTROGRAM_MIN_BANDS_REGEX);
        },
        // max bounds of each band
        [&] {
            return tryReadDoubles(m_Properties, MAX_BANDS_PROPERTY, line,
                                  SPECTROGRAM_MAX_BANDS_REGEX);
        }};

    for (auto function : functions) {
        // Stops at the first function that is valid
        if (function()) {
            return;
        }
    }
}

void SpectrogramParserHelper::readResultLine(const QString &line)
{
    tryReadResult(m_XAxisData, m_ValuesData, line, m_ValuesIndexes, m_FillValue);
}

// ////////////////// //
// VectorParserHelper //
// ////////////////// //

bool VectorParserHelper::checkProperties()
{
    return checkUnit(m_Properties, X_AXIS_UNIT_PROPERTY,
                     QObject::tr("The x-axis unit could not be found in the file"));
}

std::shared_ptr<IDataSeries> VectorParserHelper::createSeries()
{
    return std::make_shared<VectorSeries>(std::move(m_XAxisData), std::move(m_ValuesData),
                                          m_Properties.value(X_AXIS_UNIT_PROPERTY).value<Unit>(),
                                          m_Properties.value(VALUES_UNIT_PROPERTY).value<Unit>());
}

void VectorParserHelper::readPropertyLine(const QString &line)
{
    tryReadUnit(m_Properties, X_AXIS_UNIT_PROPERTY, line, DEFAULT_X_AXIS_UNIT_REGEX, true);
}

void VectorParserHelper::readResultLine(const QString &line)
{
    tryReadResult(m_XAxisData, m_ValuesData, line, valuesIndexes());
}

std::vector<int> VectorParserHelper::valuesIndexes() const
{
    // 3 values to read, in order in the file (x, y, z)
    static auto result = std::vector<int>{0, 1, 2};
    return result;
}
