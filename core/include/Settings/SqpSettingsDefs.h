#ifndef SCIQLOP_SQPSETTINGSDEFS_H
#define SCIQLOP_SQPSETTINGSDEFS_H

#include "CoreGlobal.h"

#include <QString>

// //////////////// //
// General settings //
// //////////////// //


struct SCIQLOP_CORE_EXPORT SqpSettings {
    static double toleranceValue(const QString &key, double defaultValue) noexcept;
};
extern SCIQLOP_CORE_EXPORT const QString GENERAL_TOLERANCE_AT_INIT_KEY;
extern SCIQLOP_CORE_EXPORT const double GENERAL_TOLERANCE_AT_INIT_DEFAULT_VALUE;

extern SCIQLOP_CORE_EXPORT const QString GENERAL_TOLERANCE_AT_UPDATE_KEY;
extern SCIQLOP_CORE_EXPORT const double GENERAL_TOLERANCE_AT_UPDATE_DEFAULT_VALUE;

#endif // SCIQLOP_SQPSETTINGSDEFS_H
