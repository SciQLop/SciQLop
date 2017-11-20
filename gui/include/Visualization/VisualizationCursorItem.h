#ifndef VISUALIZATIONCURSORITEM_H
#define VISUALIZATIONCURSORITEM_H

#include <Common/spimpl.h>
#include <SqpApplication.h>

class QCustomPlot;

class VisualizationCursorItem {
public:
    VisualizationCursorItem(QCustomPlot *plot);

    void setVisible(bool value);
    bool isVisible() const;

    void setPosition(double value);
    void setAbsolutePosition(double value);
    void setOrientation(Qt::Orientation orientation);
    void setLabelText(const QString &text);

private:
    class VisualizationCursorItemPrivate;
    spimpl::unique_impl_ptr<VisualizationCursorItemPrivate> impl;
};

#endif // VISUALIZATIONCURSORITEM_H
