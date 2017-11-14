#ifndef SCIQLOP_MACSCROLLBARSTYLE_H
#define SCIQLOP_MACSCROLLBARSTYLE_H

#include <QProxyStyle>

/**
 * @brief Special style to always display the scrollbars on MAC.
 */
class MacScrollBarStyle : public QProxyStyle {

public:
    int styleHint(StyleHint hint, const QStyleOption *option, const QWidget *widget,
                  QStyleHintReturn *returnData) const;

    void selfInstallOn(QWidget *widget, bool installOnSubWidgets);
};

#endif // SCIQLOP_MACSCROLLBARSTYLE_H
