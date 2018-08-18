#ifndef SCIQLOP_AMDARESULTPARSER_H
#define SCIQLOP_AMDARESULTPARSER_H

#include "AmdaGlobal.h"

#include <Data/DataSeriesType.h>

#include <QLoggingCategory>

#include <memory>

class IDataSeries;

Q_DECLARE_LOGGING_CATEGORY(LOG_AmdaResultParser)

struct SCIQLOP_AMDA_EXPORT AmdaResultParser {
    static std::shared_ptr<IDataSeries> readTxt(const QString &filePath,
                                                DataSeriesType valueType) noexcept;
    static IDataSeries* readTxt(QTextStream stream,
                                                DataSeriesType type)noexcept;
};

#endif // SCIQLOP_AMDARESULTPARSER_H
