#ifndef SCIQLOP_VARIABLEINSPECTORTABLEVIEW_H
#define SCIQLOP_VARIABLEINSPECTORTABLEVIEW_H

#include <QTableView>

class VariableInspectorTableView : public QTableView {
public:
    VariableInspectorTableView(QWidget *parent = nullptr);

protected:
    void startDrag(Qt::DropActions supportedActions);
};

#endif // SCIQLOP_VARIABLEINSPECTORTABLEVIEW_H
