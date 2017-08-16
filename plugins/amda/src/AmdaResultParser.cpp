#include "AmdaResultParser.h"

#include <Common/DateUtils.h>
#include <Data/ScalarSeries.h>

#include <QDateTime>
#include <QFile>
#include <QRegularExpression>

#include <cmath>

Q_LOGGING_CATEGORY(LOG_AmdaResultParser, "AmdaResultParser")

namespace {

/// Message in result file when the file was not found on server
const auto FILE_NOT_FOUND_MESSAGE = QStringLiteral("Not Found");

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
    dateTime.setTimeSpec(Qt::UTC);
    return dateTime.isValid() ? DateUtils::secondsSinceEpoch(dateTime)
                              : std::numeric_limits<double>::quiet_NaN();
}

/// Checks if a line is a comment line
bool isCommentLine(const QString &line)
{
    return line.startsWith("#");
}

/// @return the number of lines to be read depending on the type of value passed in parameter
int nbValues(AmdaResultParser::ValueType valueType) noexcept
{
    switch (valueType) {
        case AmdaResultParser::ValueType::SCALAR:
            return 1;
        case AmdaResultParser::ValueType::VECTOR:
            return 3;
        case AmdaResultParser::ValueType::UNKNOWN:
            // Invalid case
            break;
    }

    // Invalid cases
    qCCritical(LOG_AmdaResultParser())
        << QObject::tr("Can't get the number of values to read: unsupported type");
    return 0;
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

    // Searches unit in the comment lines
    while (stream.readLineInto(&line) && isCommentLine(line)) {
        auto match = UNIT_REGEX.match(line);
        if (match.hasMatch()) {
            return Unit{match.captured(1), true};
        }
    }

    qCWarning(LOG_AmdaResultParser()) << QObject::tr("The unit could not be found in the file");

    // Error cases
    return Unit{{}, true};
}

/**
 * Reads stream to retrieve results
 * @param stream the stream to read
 * @return the pair of vectors x-axis data/values data that has been read in the stream
 */
QPair<QVector<double>, QVector<QVector<double> > >
readResults(QTextStream &stream, AmdaResultParser::ValueType valueType)
{
    auto expectedNbValues = nbValues(valueType);

    auto xData = QVector<double>{};
    auto valuesData = QVector<QVector<double> >(expectedNbValues);

    QString line{};

    while (stream.readLineInto(&line)) {
        // Ignore comment lines
        if (!isCommentLine(line)) {
            auto lineData = line.split(RESULT_LINE_SEPARATOR, QString::SkipEmptyParts);
            if (lineData.size() == expectedNbValues + 1) {
                // X : the data is converted from date to double (in secs)
                auto x = doubleDate(lineData.at(0));

                // Adds result only if x is valid. Then, if value is invalid, it is set to NaN
                if (!std::isnan(x)) {
                    xData.push_back(x);

                    // Values
                    for (auto valueIndex = 0; valueIndex < expectedNbValues; ++valueIndex) {
                        auto column = valueIndex + 1;

                        bool valueOk;
                        auto value = lineData.at(column).toDouble(&valueOk);

                        if (!valueOk) {
                            qCWarning(LOG_AmdaResultParser())
                                << QObject::tr(
                                       "Value from (line %1, column %2) is invalid and will be "
                                       "converted to NaN")
                                       .arg(line, column);
                            value = std::numeric_limits<double>::quiet_NaN();
                        }
                        valuesData[valueIndex].append(value);
                    }
                }
                else {
                    qCWarning(LOG_AmdaResultParser())
                        << QObject::tr("Can't retrieve results from line %1: x is invalid")
                               .arg(line);
                }
            }
            else {
                qCWarning(LOG_AmdaResultParser())
                    << QObject::tr("Can't retrieve results from line %1: invalid line").arg(line);
            }
        }
    }

    return qMakePair(std::move(xData), std::move(valuesData));
}

} // namespace

std::shared_ptr<IDataSeries> AmdaResultParser::readTxt(const QString &filePath,
                                                       ValueType valueType) noexcept
{
    if (valueType == ValueType::UNKNOWN) {
        qCCritical(LOG_AmdaResultParser())
            << QObject::tr("Can't retrieve AMDA data: the type of values to be read is unknown");
        return nullptr;
    }

    QFile file{filePath};

    if (!file.open(QFile::ReadOnly | QIODevice::Text)) {
        qCCritical(LOG_AmdaResultParser())
            << QObject::tr("Can't retrieve AMDA data from file %1: %2")
                   .arg(filePath, file.errorString());
        return nullptr;
    }

    QTextStream stream{&file};

    // Checks if the file was found on the server
    auto firstLine = stream.readLine();
    if (firstLine.compare(FILE_NOT_FOUND_MESSAGE) == 0) {
        qCCritical(LOG_AmdaResultParser())
            << QObject::tr("Can't retrieve AMDA data from file %1: file was not found on server")
                   .arg(filePath);
        return nullptr;
    }

    // Reads x-axis unit
    stream.seek(0); // returns to the beginning of the file
    auto xAxisUnit = readXAxisUnit(stream);

    // Reads results
    stream.seek(0); // returns to the beginning of the file
    auto results = readResults(stream, valueType);


    return std::make_shared<ScalarSeries>(std::move(results.first), std::move(results.second),
                                          xAxisUnit, Unit{});
}
