#ifndef SCIQLOP_COLORUTILS_H
#define SCIQLOP_COLORUTILS_H

#include <vector>

class QColor;

/**
 * Utility class with methods for colors
 */
struct ColorUtils {
    /// Generates a color scale from min / max values and a number of colors.
    /// The algorithm uses the HSV color model to generate color variations (see
    /// http://doc.qt.io/qt-4.8/qcolor.html#the-hsv-color-model)
    static std::vector<QColor> colors(const QColor &minColor, const QColor &maxColor,
                                      int nbColors) noexcept;
};

#endif // SCIQLOP_COLORUTILS_H
