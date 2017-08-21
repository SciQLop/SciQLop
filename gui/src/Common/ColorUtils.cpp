#include "Common/ColorUtils.h"

#include <QtGui/QColor>

std::vector<QColor> ColorUtils::colors(const QColor &minColor, const QColor &maxColor,
                                       int nbColors) noexcept
{
    auto result = std::vector<QColor>{};

    if (nbColors == 1) {
        result.push_back(minColor);
    }
    else if (nbColors > 0) {
        const auto nbSteps = static_cast<double>(nbColors - 1);

        const auto colorHStep = (maxColor.hue() - minColor.hue()) / nbSteps;
        const auto colorSStep = (maxColor.saturation() - minColor.saturation()) / nbSteps;
        const auto colorVStep = (maxColor.value() - minColor.value()) / nbSteps;
        const auto colorAStep = (maxColor.alpha() - minColor.alpha()) / nbSteps;

        for (auto i = 0; i < nbColors; ++i) {
            result.push_back(QColor::fromHsv(
                minColor.hue() + i * colorHStep, minColor.saturation() + i * colorSStep,
                minColor.value() + i * colorVStep, minColor.alpha() + i * colorAStep));
        }
    }

    return result;
}
