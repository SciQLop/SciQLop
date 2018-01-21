#ifndef SCIQLOP_DATASERIESTYPE_H
#define SCIQLOP_DATASERIESTYPE_H

#include <QString>

enum class DataSeriesType { SCALAR, SPECTROGRAM, VECTOR, UNKNOWN };

struct DataSeriesTypeUtils {
    static DataSeriesType fromString(const QString &type)
    {
        if (type == QStringLiteral("scalar")) {
            return DataSeriesType::SCALAR;
        }
        else if (type == QStringLiteral("spectrogram")) {
            return DataSeriesType::SPECTROGRAM;
        }
        else if (type == QStringLiteral("vector")) {
            return DataSeriesType::VECTOR;
        }
        else {
            return DataSeriesType::UNKNOWN;
        }
    }
};

#endif // SCIQLOP_DATASERIESTYPE_H
