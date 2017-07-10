#include "AmdaResultParser.h"

#include <Data/ScalarSeries.h>

#include <QDateTime>
#include <QFile>

Q_LOGGING_CATEGORY(LOG_AmdaResultParser, "AmdaResultParser")

namespace {

/// Format for dates in result files
const auto DATE_FORMAT = QStringLiteral("yyyy-MM-ddThh:mm:ss.zzz");

/// @todo ALX
double doubleDate(const QString &stringDate) noexcept
{
    auto dateTime = QDateTime::fromString(stringDate, DATE_FORMAT);
    return dateTime.toMSecsSinceEpoch() / 1000.;
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

    // Ignore comment lines (3 lines)
    stream.readLine();
    stream.readLine();
    stream.readLine();

    QString line{};
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

    /// @todo ALX : handle units
    return std::make_shared<ScalarSeries>(std::move(xData), std::move(valuesData), Unit{"nT", true},
                                          Unit{});
}
