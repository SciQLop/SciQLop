#include "AmdaResultParserHelper.h"

#include <Data/Unit.h>

Q_LOGGING_CATEGORY(LOG_AmdaResultParserHelper, "AmdaResultParserHelper")

namespace {

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
    /// @todo ALX
}

void ScalarParserHelper::readPropertyLine(const QString &line)
{
    tryReadUnit(m_Properties, X_AXIS_UNIT_PROPERTY, line, DEFAULT_X_AXIS_UNIT_REGEX, true);
}

void ScalarParserHelper::readResultLine(const QString &line)
{
    /// @todo ALX
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
    /// @todo ALX
}

void VectorParserHelper::readPropertyLine(const QString &line)
{
    tryReadUnit(m_Properties, X_AXIS_UNIT_PROPERTY, line, DEFAULT_X_AXIS_UNIT_REGEX, true);
}

void VectorParserHelper::readResultLine(const QString &line)
{
    /// @todo ALX
}
