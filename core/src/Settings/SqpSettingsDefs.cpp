#include "Settings/SqpSettingsDefs.h"

#include <QSettings>


/// Gets a tolerance value from application settings. If the setting can't be found, the default
/// value passed in parameter is returned
double SqpSettings::toleranceValue(const QString &key, double defaultValue) noexcept
{
    return QSettings{}.value(key, defaultValue).toDouble();
}


const QString GENERAL_TOLERANCE_AT_INIT_KEY = QStringLiteral("toleranceInit");
const double GENERAL_TOLERANCE_AT_INIT_DEFAULT_VALUE = 0.2;

const QString GENERAL_TOLERANCE_AT_UPDATE_KEY = QStringLiteral("toleranceUpdate");
const double GENERAL_TOLERANCE_AT_UPDATE_DEFAULT_VALUE = 0.2;
