#include "AmdaResultParserDefs.h"

const QString END_TIME_PROPERTY = QStringLiteral("endTime");
const QString FILL_VALUE_PROPERTY = QStringLiteral("fillValue");
const QString MAX_BANDS_PROPERTY = QStringLiteral("maxBands");
const QString MIN_BANDS_PROPERTY = QStringLiteral("minBands");
const QString MAX_SAMPLING_PROPERTY = QStringLiteral("maxSampling");
const QString MIN_SAMPLING_PROPERTY = QStringLiteral("minSampling");
const QString START_TIME_PROPERTY = QStringLiteral("startTime");
const QString X_AXIS_UNIT_PROPERTY = QStringLiteral("xAxisUnit");
const QString Y_AXIS_UNIT_PROPERTY = QStringLiteral("yAxisUnit");
const QString VALUES_UNIT_PROPERTY = QStringLiteral("valuesUnit");

namespace {

const auto PARAMETER_UNITS_REGEX
    = QRegularExpression{QStringLiteral("\\s*PARAMETER_UNITS\\s*:\\s*(.*)")};
}

const QRegularExpression DEFAULT_X_AXIS_UNIT_REGEX
    = QRegularExpression{QStringLiteral("-\\s*Units\\s*:\\s*(.+?)\\s*-")};

const QRegularExpression ALTERNATIVE_X_AXIS_UNIT_REGEX = PARAMETER_UNITS_REGEX;

const QRegularExpression SPECTROGRAM_END_TIME_REGEX
    = QRegularExpression{QStringLiteral("\\s*INTERVAL_STOP\\s*:\\s*(.*)")};

const QRegularExpression SPECTROGRAM_FILL_VALUE_REGEX
    = QRegularExpression{QStringLiteral("\\s*PARAMETER_FILL_VALUE\\s*:\\s*(.*)")};

const QRegularExpression SPECTROGRAM_MAX_BANDS_REGEX
    = QRegularExpression{QStringLiteral("\\s*PARAMETER_TABLE_MAX_VALUES\\[0\\]\\s*:\\s*(.*)")};

const QRegularExpression SPECTROGRAM_MIN_BANDS_REGEX
    = QRegularExpression{QStringLiteral("\\s*PARAMETER_TABLE_MIN_VALUES\\[0\\]\\s*:\\s*(.*)")};

const QRegularExpression SPECTROGRAM_MAX_SAMPLING_REGEX
    = QRegularExpression{QStringLiteral("\\s*DATASET_MAX_SAMPLING\\s*:\\s*(.*)")};

const QRegularExpression SPECTROGRAM_MIN_SAMPLING_REGEX
    = QRegularExpression{QStringLiteral("\\s*DATASET_MIN_SAMPLING\\s*:\\s*(.*)")};

const QRegularExpression SPECTROGRAM_START_TIME_REGEX
    = QRegularExpression{QStringLiteral("\\s*INTERVAL_START\\s*:\\s*(.*)")};

const QRegularExpression SPECTROGRAM_Y_AXIS_UNIT_REGEX
    = QRegularExpression{QStringLiteral("\\s*PARAMETER_TABLE_UNITS\\[0\\]\\s*:\\s*(.*)")};

const QRegularExpression SPECTROGRAM_VALUES_UNIT_REGEX = PARAMETER_UNITS_REGEX;
