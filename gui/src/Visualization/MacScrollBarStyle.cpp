#include "Visualization/MacScrollBarStyle.h"

#include <QWidget>

int MacScrollBarStyle::styleHint(QStyle::StyleHint hint, const QStyleOption *option,
                                 const QWidget *widget, QStyleHintReturn *returnData) const
{
    switch (hint) {
        case SH_ScrollBar_Transient:
            return false; // Makes the scrollbar always visible
        case SH_ScrollView_FrameOnlyAroundContents:
            return true; // Avoid that the scrollbar is drawn on top of the widget
        default:
            break;
    }

    return QProxyStyle::styleHint(hint, option, widget, returnData);
}

void MacScrollBarStyle::selfInstallOn(QWidget *widget, bool installOnSubWidgets)
{
    // Note: a style can be installed on a particular widget but it is not automatically applied its
    // children widgets.

    QList<QWidget *> widgetsToStyle{widget};
    while (!widgetsToStyle.isEmpty()) {

        auto widget = widgetsToStyle.takeFirst();
        widget->setStyle(this);

        if (installOnSubWidgets) {
            for (auto child : widget->children()) {
                auto childWidget = qobject_cast<QWidget *>(child);
                if (childWidget) {
                    widgetsToStyle << childWidget;
                }
            }
        }
    }
}
