#ifndef SCIQLOP_VISUALIZATIONSELECTIONZONEITEM_H
#define SCIQLOP_VISUALIZATIONSELECTIONZONEITEM_H

#include <Common/spimpl.h>
#include <Data/SqpRange.h>
#include <Visualization/qcustomplot.h>

class VisualizationSelectionZoneItem : public QCPItemRect {

public:
    VisualizationSelectionZoneItem(QCustomPlot *plot);
    virtual ~VisualizationSelectionZoneItem();

    void setName(const QString &name);
    QString name() const;

    SqpRange range() const;
    void setRange(double tstart, double tend);
    void setStart(double tstart);
    void setEnd(double tend);

    void setColor(const QColor &color);

    void setEditionEnabled(bool value);
    bool isEditionEnabled() const;

    Qt::CursorShape curshorShapeForPosition(const QPoint &position) const;
    void setHovered(bool value);

    void setAssociatedEditedZones(const QVector<VisualizationSelectionZoneItem *> &associatedZones);

protected:
    void mousePressEvent(QMouseEvent *event, const QVariant &details) override;
    void mouseMoveEvent(QMouseEvent *event, const QPointF &startPos) override;
    void mouseReleaseEvent(QMouseEvent *event, const QPointF &startPos) override;

    void resizeLeft(double pixelDiff);
    void resizeRight(double pixelDiff);
    void move(double pixelDiff);


private:
    class VisualizationSelectionZoneItemPrivate;
    spimpl::unique_impl_ptr<VisualizationSelectionZoneItemPrivate> impl;
};

#endif // SCIQLOP_VISUALIZATIONSELECTIONZONEITEM_H
