#include "AmdaResultParser.h"

#include <Data/ScalarSeries.h>

#include <QDateTime>
#include <QFile>
#include <QRegularExpression>

Q_LOGGING_CATEGORY(LOG_AmdaResultParser, "AmdaResultParser")

namespace {

/// Format for dates in result files
const auto DATE_FORMAT = QStringLiteral("yyyy-MM-ddThh:mm:ss.zzz");

/// Regex to find unit in a line. Examples of valid lines:
/// ... - Units : nT - ...
/// ... -Units:nT- ...
/// ... -Units:   m²- ...
/// ... - Units : m/s - ...
const auto UNIT_REGEX = QRegularExpression{QStringLiteral("-\\s*Units\\s*:\\s*(.+?)\\s*-")};

/// @todo ALX
double doubleDate(const QString &stringDate) noexcept
{
    auto dateTime = QDateTime::fromString(stringDate, DATE_FORMAT);
    return dateTime.toMSecsSinceEpoch() / 1000.;
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

    auto xData = QVector<double>{};
    auto valuesData = QVector<double>{};

    QTextStream stream{&file};

    // Ignore first two lines (comments lines)
    stream.readLine();
    stream.readLine();

    QString line{};

    // Reads x-axis unit
    auto xAxisUnit = readXAxisUnit(stream);

    // Reads results
    auto lineRegex = QRegExp{QStringLiteral("\\s+")};
    while (stream.readLineInto(&line)) {
        auto lineData = line.split(lineRegex, QString::SkipEmptyParts);
        if (lineData.size() == 2) {
            // X : the data is converted from date to double (in secs)
            xData.push_back(doubleDate(lineData.at(0)));

            // Value
            valuesData.push_back(lineData.at(1).toDouble());
        }
        else {
            /// @todo ALX : log
        }
    }

    return std::make_shared<ScalarSeries>(std::move(xData), std::move(valuesData), xAxisUnit,
                                          Unit{});
}
