#include "AmdaResultParserDefs.h"

const QString X_AXIS_UNIT_PROPERTY = QStringLiteral("xAxisUnit");

const QRegularExpression DEFAULT_X_AXIS_UNIT_REGEX
    = QRegularExpression{QStringLiteral("-\\s*Units\\s*:\\s*(.+?)\\s*-")};
