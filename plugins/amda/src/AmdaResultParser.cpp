#include "AmdaResultParser.h"

#include "AmdaResultParserHelper.h"

#include <QFile>

#include <cmath>

Q_LOGGING_CATEGORY(LOG_AmdaResultParser, "AmdaResultParser")

namespace
{

/// Message in result file when the file was not found on server
const auto FILE_NOT_FOUND_MESSAGE = QStringLiteral("Not Found");

/// Checks if a line is a comment line
bool isCommentLine(const QString& line)
{
    return line.startsWith("#");
}

/**
 * Creates helper that will be used to read AMDA file, according to the type passed as parameter
 * @param valueType the type of values expected in the AMDA file (scalars, vectors, spectrograms...)
 * @return the helper created
 */
std::unique_ptr<IAmdaResultParserHelper> createHelper(DataSeriesType valueType)
{
    switch (valueType)
    {
        case DataSeriesType::SCALAR:
            return std::make_unique<ScalarParserHelper>();
        case DataSeriesType::SPECTROGRAM:
            return std::make_unique<SpectrogramParserHelper>();
        case DataSeriesType::VECTOR:
            return std::make_unique<VectorParserHelper>();
        case DataSeriesType::NONE:
            // Invalid case
            break;
    }

    // Invalid cases
    qCCritical(LOG_AmdaResultParser())
        << QObject::tr("Can't create helper to read result file: unsupported type");
    return nullptr;
}

/**
 * Reads properties of the stream passed as parameter
 * @param helper the helper used to read properties line by line
 * @param stream the stream to read
 */
void readProperties(IAmdaResultParserHelper& helper, QTextStream& stream)
{
    // Searches properties in the comment lines (as long as the reading has not reached the data)
    // AMDA V2: while (stream.readLineInto(&line) && !line.contains(DATA_HEADER_REGEX)) {
    QString line {};
    while (stream.readLineInto(&line) && isCommentLine(line))
    {
        helper.readPropertyLine(line);
    }
}

/**
 * Reads results of the stream passed as parameter
 * @param helper the helper used to read results line by line
 * @param stream the stream to read
 */
void readResults(IAmdaResultParserHelper& helper, QTextStream& stream)
{
    QString line {};

    // Skip comment lines
    while (stream.readLineInto(&line) && isCommentLine(line))
    {
    }

    if (!stream.atEnd())
    {
        do
        {
            helper.readResultLine(line);
        } while (stream.readLineInto(&line));
    }
}

} // namespace

std::shared_ptr<IDataSeries> AmdaResultParser::readTxt(
    const QString& filePath, DataSeriesType type) noexcept
{
    if (type == DataSeriesType::NONE)
    {
        qCCritical(LOG_AmdaResultParser())
            << QObject::tr("Can't retrieve AMDA data: the type of values to be read is unknown");
        return nullptr;
    }

    QFile file { filePath };

    if (!file.open(QFile::ReadOnly | QIODevice::Text))
    {
        qCCritical(LOG_AmdaResultParser())
            << QObject::tr("Can't retrieve AMDA data from file %1: %2")
                   .arg(filePath, file.errorString());
        return nullptr;
    }

    return std::shared_ptr<IDataSeries> { AmdaResultParser::readTxt(QTextStream { &file }, type) };
}

IDataSeries* AmdaResultParser::readTxt(QTextStream stream, DataSeriesType type) noexcept
{
    if (type == DataSeriesType::NONE)
    {
        return nullptr;
    }

    // Checks if the file was found on the server
    auto firstLine = stream.readLine();
    if (firstLine.compare(FILE_NOT_FOUND_MESSAGE) == 0)
    {
        return nullptr;
    }

    auto helper = createHelper(type);
    Q_ASSERT(helper != nullptr);

    // Reads header file to retrieve properties
    stream.seek(0); // returns to the beginning of the file
    readProperties(*helper, stream);

    // Checks properties
    if (helper->checkProperties())
    {
        // Reads results
        // AMDA V2: remove line
        stream.seek(0); // returns to the beginning of the file
        readResults(*helper, stream);

        // Creates data series
        return helper->createSeries();
    }
    else
    {
        return nullptr;
    }
}
