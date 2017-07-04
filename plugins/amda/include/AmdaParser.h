#ifndef SCIQLOP_AMDAPARSER_H
#define SCIQLOP_AMDAPARSER_H

#include "AmdaGlobal.h"

#include <QLoggingCategory>

#include <memory>

Q_DECLARE_LOGGING_CATEGORY(LOG_AmdaParser)

class DataSourceItem;

struct SCIQLOP_AMDA_EXPORT AmdaParser {
    /**
     * Creates a data source tree from a JSON file
     * @param filePath the path of the JSON file to read
     * @return the root of the created data source tree, nullptr if the file couldn't be parsed
     */
    static std::unique_ptr<DataSourceItem> readJson(const QString &filePath) noexcept;
};

#endif // SCIQLOP_AMDAPARSER_H
