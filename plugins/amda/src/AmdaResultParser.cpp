#include "AmdaResultParser.h"

#include <Data/ScalarSeries.h>

#include <QDateTime>
#include <QFile>
#include <QRegularExpression>

Q_LOGGING_CATEGORY(LOG_AmdaResultParser, "AmdaResultParser")

namespace {

/// Format for dates in result files
const auto DATE_FORMAT = QStringLiteral("yyyy-MM-ddThh:mm:ss.zzz");

/// Separator between values in a result line
const auto RESULT_LINE_SEPARATOR = QRegularExpression{QStringLiteral("\\s+")};

/// Regex to find unit in a line. Examples of valid lines:
/// ... - Units : nT - ...
/// ... -Units:nT- ...
/// ... -Units:   m²- ...
/// ... - Units : m/s - ...
const auto UNIT_REGEX = QRegularExpression{QStringLiteral("-\\s*Units\\s*:\\s*(.+?)\\s*-")};

/// Converts a string date to a double date
/// @return a double that represents the date in seconds, NaN if the string date can't be converted
double doubleDate(const QString &stringDate) noexcept
{
    auto dateTime = QDateTime::fromString(stringDate, DATE_FORMAT);
    return dateTime.isValid() ? (dateTime.toMSecsSinceEpoch() / 1000.)
                              : std::numeric_limits<double>::quiet_NaN();
}

/**
 * Reads stream to retrieve x-axis unit
 * @param stream the stream to read
 * @return the unit that has been read in the stream, a default unit (time unit with no label) if an
 * error occured during reading
 */
Unit readXAxisUnit(QTextStream &stream)
{
    QString line{};

    if (stream.readLineInto(&line)) {
        auto match = UNIT_REGEX.match(line);
        if (match.hasMatch()) {
            return Unit{match.captured(1), true};
        }
        else {
            qCWarning(LOG_AmdaResultParser())
                << QObject::tr("Can't read unit: invalid line %1").arg(line);
        }
    }
    else {
        qCWarning(LOG_AmdaResultParser()) << QObject::tr("Can't read unit: end of file");
    }

    // Error cases
    return Unit{{}, true};
}

/**
 * Reads stream to retrieve results
 * @param stream the stream to read
 * @return the pair of vectors x-axis data/values data that has been read in the stream
 */
QPair<QVector<double>, QVector<double> > readResults(QTextStream &stream)
{
    auto xData = QVector<double>{};
    auto valuesData = QVector<double>{};

    QString line{};
    while (stream.readLineInto(&line)) {
        auto lineData = line.split(RESULT_LINE_SEPARATOR, QString::SkipEmptyParts);
        if (lineData.size() == 2) {
            // X : the data is converted from date to double (in secs)
            auto x = doubleDate(lineData.at(0));

            // Value
            bool valueOk;
            auto value = lineData.at(1).toDouble(&valueOk);

            // Adds result only if x and value are valid
            if (!std::isnan(x) && !std::isnan(value) && valueOk) {
                xData.push_back(x);
                valuesData.push_back(value);
            }
            else {
                qCWarning(LOG_AmdaResultParser())
                    << QObject::tr(
                           "Can't retrieve results from line %1: x and/or value are invalid")
                           .arg(line);
            }
        }
        else {
            qCWarning(LOG_AmdaResultParser())
                << QObject::tr("Can't retrieve results from line %1: invalid line").arg(line);
        }
    }

    return qMakePair(std::move(xData), std::move(valuesData));
}

} // namespace

std::shared_ptr<IDataSeries> AmdaResultParser::readTxt(const QString &filePath) noexcept
{
    QFile file{filePath};

    if (!file.open(QFile::ReadOnly | QIODevice::Text)) {
        qCCritical(LOG_AmdaResultParser())
            << QObject::tr("Can't retrieve AMDA data from file %1: %2")
                   .arg(filePath, file.errorString());
        return nullptr;
    }

    QTextStream stream{&file};

    // Ignore first two lines (comments lines)
    stream.readLine();
    stream.readLine();

    // Reads x-axis unit
    auto xAxisUnit = readXAxisUnit(stream);

    // Reads results
    auto results = readResults(stream);

    return std::make_shared<ScalarSeries>(std::move(results.first), std::move(results.second),
                                          xAxisUnit, Unit{});
}
