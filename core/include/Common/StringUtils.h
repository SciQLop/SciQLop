#ifndef SCIQLOP_STRINGUTILS_H
#define SCIQLOP_STRINGUTILS_H

#include "CoreGlobal.h"

#include <vector>

class QString;

/**
 * Utility class with methods for strings
 */
struct SCIQLOP_CORE_EXPORT StringUtils {
    /**
     * Generates a unique name from a default name and a set of forbidden names.
     *
     * Generating the unique name is done by adding an index to the default name and stopping at the
     * first index for which the generated name is not in the forbidden names.
     *
     * Examples (defaultName, forbiddenNames -> result):
     * - "FGM", {"FGM"} -> "FGM1"
     * - "FGM", {"ABC"} -> "FGM"
     * - "FGM", {"FGM", "FGM1"} -> "FGM2"
     * - "FGM", {"FGM", "FGM2"} -> "FGM1"
     * - "", {"ABC"} -> "1"
     *
     * @param defaultName the default name
     * @param forbiddenNames the set of forbidden names
     * @return the unique name generated
     */
    static QString uniqueName(const QString &defaultName,
                              const std::vector<QString> &forbiddenNames) noexcept;
};

#endif // SCIQLOP_STRINGUTILS_H
