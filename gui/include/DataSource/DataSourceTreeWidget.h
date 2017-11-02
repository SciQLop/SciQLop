#ifndef SCIQLOP_DATASOURCETREEWIDGET_H
#define SCIQLOP_DATASOURCETREEWIDGET_H

#include <QTreeWidget>

class DataSourceTreeWidget : public QTreeWidget {
public:
    DataSourceTreeWidget(QWidget *parent);

protected:
    QMimeData *mimeData(const QList<QTreeWidgetItem *> items) const override;
    void startDrag(Qt::DropActions supportedActions) override;
};

#endif // SCIQLOP_DATASOURCETREEWIDGET_H
