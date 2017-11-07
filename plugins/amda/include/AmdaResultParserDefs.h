#ifndef SCIQLOP_AMDARESULTPARSERDEFS_H
#define SCIQLOP_AMDARESULTPARSERDEFS_H

#include <QtCore/QRegularExpression>
#include <QtCore/QString>
#include <QtCore/QVariantHash>

// ////////// //
// Properties //
// ////////// //

/// Alias to represent properties read in the header of AMDA file
using Properties = QVariantHash;

extern const QString X_AXIS_UNIT_PROPERTY;

// /////////////////// //
// Regular expressions //
// /////////////////// //

// AMDA V2
// /// Regex to find the header of the data in the file. This header indicates the end of comments
// in the file
// const auto DATA_HEADER_REGEX = QRegularExpression{QStringLiteral("#\\s*DATA\\s*:")};

// AMDA V2
// /// ... PARAMETER_UNITS : nT ...
// /// ... PARAMETER_UNITS:nT ...
// /// ... PARAMETER_UNITS:   m² ...
// /// ... PARAMETER_UNITS : m/s ...
// const auto UNIT_REGEX = QRegularExpression{QStringLiteral("\\s*PARAMETER_UNITS\\s*:\\s*(.+)")};

/// Regex to find x-axis unit in a line. Examples of valid lines:
/// ... - Units : nT - ...
/// ... -Units:nT- ...
/// ... -Units:   m²- ...
/// ... - Units : m/s - ...
extern const QRegularExpression DEFAULT_X_AXIS_UNIT_REGEX;

#endif // SCIQLOP_AMDARESULTPARSERDEFS_H
