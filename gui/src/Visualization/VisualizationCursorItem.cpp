#include <Common/DateUtils.h>
#include <Visualization/VisualizationCursorItem.h>
#include <Visualization/qcustomplot.h>

/// Width of the cursor in pixel
const auto CURSOR_WIDTH = 3;

/// Color of the cursor in the graph
const auto CURSOR_COLOR = QColor{68, 114, 196};

/// Line style of the cursor in the graph
auto CURSOR_PEN_STYLE = Qt::DotLine;

struct VisualizationCursorItem::VisualizationCursorItemPrivate {

    QCustomPlot *m_Plot = nullptr;

    QCPItemStraightLine *m_LineItem = nullptr;
    QCPItemText *m_LabelItem = nullptr;

    Qt::Orientation m_Orientation;
    double m_Position = 0.0;
    bool m_IsAbsolutePosition = false;
    QString m_LabelText;

    explicit VisualizationCursorItemPrivate(QCustomPlot *plot)
            : m_Plot(plot), m_Orientation(Qt::Vertical)
    {
    }

    void updateOrientation()
    {
        if (m_LineItem) {
            switch (m_Orientation) {
                case Qt::Vertical:
                    m_LineItem->point1->setTypeX(m_IsAbsolutePosition
                                                     ? QCPItemPosition::ptAbsolute
                                                     : QCPItemPosition::ptPlotCoords);
                    m_LineItem->point1->setTypeY(QCPItemPosition::ptAxisRectRatio);
                    m_LineItem->point2->setTypeX(m_IsAbsolutePosition
                                                     ? QCPItemPosition::ptAbsolute
                                                     : QCPItemPosition::ptPlotCoords);
                    m_LineItem->point2->setTypeY(QCPItemPosition::ptAxisRectRatio);
                    m_LabelItem->setPositionAlignment(Qt::AlignLeft | Qt::AlignTop);
                    break;
                case Qt::Horizontal:
                    m_LineItem->point1->setTypeX(QCPItemPosition::ptAxisRectRatio);
                    m_LineItem->point1->setTypeY(m_IsAbsolutePosition
                                                     ? QCPItemPosition::ptAbsolute
                                                     : QCPItemPosition::ptPlotCoords);
                    m_LineItem->point2->setTypeX(QCPItemPosition::ptAxisRectRatio);
                    m_LineItem->point2->setTypeY(m_IsAbsolutePosition
                                                     ? QCPItemPosition::ptAbsolute
                                                     : QCPItemPosition::ptPlotCoords);
                    m_LabelItem->setPositionAlignment(Qt::AlignRight | Qt::AlignBottom);
            }
        }
    }

    void updateCursorPosition()
    {
        if (m_LineItem) {
            switch (m_Orientation) {
                case Qt::Vertical:
                    m_LineItem->point1->setCoords(m_Position, 0);
                    m_LineItem->point2->setCoords(m_Position, 1);
                    m_LabelItem->position->setCoords(5, 5);
                    break;
                case Qt::Horizontal:
                    m_LineItem->point1->setCoords(1, m_Position);
                    m_LineItem->point2->setCoords(0, m_Position);
                    m_LabelItem->position->setCoords(-5, -5);
            }
        }
    }

    void updateLabelText()
    {
        if (m_LabelItem) {
            m_LabelItem->setText(m_LabelText);
        }
    }
};

VisualizationCursorItem::VisualizationCursorItem(QCustomPlot *plot)
        : impl{spimpl::make_unique_impl<VisualizationCursorItemPrivate>(plot)}
{
}

void VisualizationCursorItem::setVisible(bool value)
{
    if (value != isVisible()) {

        if (value) {
            Q_ASSERT(!impl->m_LineItem && !impl->m_LabelItem);

            impl->m_LineItem = new QCPItemStraightLine{impl->m_Plot};
            auto pen = QPen{CURSOR_PEN_STYLE};
            pen.setColor(CURSOR_COLOR);
            pen.setWidth(CURSOR_WIDTH);
            impl->m_LineItem->setPen(pen);
            impl->m_LineItem->setSelectable(false);

            impl->m_LabelItem = new QCPItemText{impl->m_Plot};
            impl->m_LabelItem->setColor(CURSOR_COLOR);
            impl->m_LabelItem->setSelectable(false);
            impl->m_LabelItem->position->setParentAnchor(impl->m_LineItem->point1);
            impl->m_LabelItem->position->setTypeX(QCPItemPosition::ptAbsolute);
            impl->m_LabelItem->position->setTypeY(QCPItemPosition::ptAbsolute);

            auto font = impl->m_LabelItem->font();
            font.setPointSize(10);
            font.setBold(true);
            impl->m_LabelItem->setFont(font);

            impl->updateOrientation();
            impl->updateLabelText();
            impl->updateCursorPosition();
        }
        else {
            Q_ASSERT(impl->m_LineItem && impl->m_LabelItem);

            // Note: the items are destroyed by QCustomPlot in removeItem
            impl->m_Plot->removeItem(impl->m_LineItem);
            impl->m_LineItem = nullptr;
            impl->m_Plot->removeItem(impl->m_LabelItem);
            impl->m_LabelItem = nullptr;
        }
    }
}

bool VisualizationCursorItem::isVisible() const
{
    return impl->m_LineItem != nullptr;
}

void VisualizationCursorItem::setPosition(double value)
{
    impl->m_Position = value;
    impl->m_IsAbsolutePosition = false;
    impl->updateLabelText();
    impl->updateCursorPosition();
}

void VisualizationCursorItem::setAbsolutePosition(double value)
{
    setPosition(value);
    impl->m_IsAbsolutePosition = true;
}

void VisualizationCursorItem::setOrientation(Qt::Orientation orientation)
{
    impl->m_Orientation = orientation;
    impl->updateLabelText();
    impl->updateOrientation();
    impl->updateCursorPosition();
}

void VisualizationCursorItem::setLabelText(const QString &text)
{
    impl->m_LabelText = text;
    impl->updateLabelText();
}
