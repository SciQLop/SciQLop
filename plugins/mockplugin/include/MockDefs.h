#ifndef SCIQLOP_MOCKDEFS_H
#define SCIQLOP_MOCKDEFS_H

#include "MockPluginGlobal.h"

#include <QString>
#include <QVariant>

// ////////////// //
// Mock constants //
// ////////////// //

// Metadata for cosinus provider //

/// Cosinus frequency (Hz)
extern SCIQLOP_MOCKPLUGIN_EXPORT const QString COSINUS_FREQUENCY_KEY;
extern SCIQLOP_MOCKPLUGIN_EXPORT const QVariant COSINUS_FREQUENCY_DEFAULT_VALUE;

/// Cosinus type ("scalar" or "vector")
extern SCIQLOP_MOCKPLUGIN_EXPORT const QString COSINUS_TYPE_KEY;
extern SCIQLOP_MOCKPLUGIN_EXPORT const QVariant COSINUS_TYPE_DEFAULT_VALUE;

#endif // SCIQLOP_MOCKDEFS_H
