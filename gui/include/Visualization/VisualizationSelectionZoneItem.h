#ifndef SCIQLOP_VISUALIZATIONSELECTIONZONEITEM_H
#define SCIQLOP_VISUALIZATIONSELECTIONZONEITEM_H

#include <Common/spimpl.h>
#include <Data/SqpRange.h>
#include <Visualization/qcustomplot.h>

class VisualizationGraphWidget;

class VisualizationSelectionZoneItem : public QCPItemRect {

public:
    VisualizationSelectionZoneItem(QCustomPlot *plot);
    virtual ~VisualizationSelectionZoneItem();

    VisualizationGraphWidget *parentGraphWidget() const noexcept;

    void setName(const QString &name);
    QString name() const;

    SqpRange range() const;
    void setRange(double tstart, double tend);
    void setStart(double tstart);
    void setEnd(double tend);

    void setColor(const QColor &color);

    void setEditionEnabled(bool value);
    bool isEditionEnabled() const;

    /// Moves the item at the top of its QCPLayer. It will then receive the mouse events if multiple
    /// items are stacked on top of each others.
    void moveToTop();

    Qt::CursorShape curshorShapeForPosition(const QPoint &position) const;
    void setHovered(bool value);

    /// Sets the zones which should be moved or reisized together with this zone
    void setAssociatedEditedZones(const QVector<VisualizationSelectionZoneItem *> &associatedZones);

    /// Align the specified zones with this one, vertically with the left border
    bool alignZonesVerticallyOnLeft(const QVector<VisualizationSelectionZoneItem *> &zonesToAlign,
                                    bool allowResize);
    /// Align the specified zones with this one, vertically with the right border
    bool alignZonesVerticallyOnRight(const QVector<VisualizationSelectionZoneItem *> &zonesToAlign,
                                     bool allowResize);
    /// Align the specified zones with this one, temporally with the left border
    bool alignZonesTemporallyOnLeft(const QVector<VisualizationSelectionZoneItem *> &zonesToAlign,
                                    bool allowResize);
    /// Align the specified zones with this one, temporally with the right border
    bool alignZonesTemporallyOnRight(const QVector<VisualizationSelectionZoneItem *> &zonesToAlign,
                                     bool allowResize);

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
