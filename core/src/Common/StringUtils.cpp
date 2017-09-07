#include "Common/StringUtils.h"

#include <QRegExp>
#include <QString>

#include <set>

QString StringUtils::uniqueName(const QString &defaultName,
                                const std::vector<QString> &forbiddenNames) noexcept
{
    // Gets the base of the unique name to generate, by removing trailing number (for example, base
    // name of "FGM12" is "FGM")
    auto baseName = defaultName;
    baseName.remove(QRegExp{QStringLiteral("\\d*$")});

    // Finds the unique name by adding an index to the base name and stops when the generated name
    // isn't forbidden
    QString newName{};
    auto forbidden = true;
    for (auto i = 0; forbidden; ++i) {
        newName = (i == 0) ? baseName : baseName + QString::number(i);
        forbidden = newName.isEmpty()
                    || std::any_of(forbiddenNames.cbegin(), forbiddenNames.cend(),
                                   [&newName](const auto &name) {
                                       return name.compare(newName, Qt::CaseInsensitive) == 0;
                                   });
    }

    return newName;
}
