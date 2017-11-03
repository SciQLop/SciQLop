#include "Variable/VariableInspectorTableView.h"

#include "DragDropHelper.h"
#include "SqpApplication.h"

VariableInspectorTableView::VariableInspectorTableView(QWidget *parent) : QTableView(parent) {}

void VariableInspectorTableView::startDrag(Qt::DropActions supportedActions)
{
    // Resets the drag&drop operations before it's starting
    sqpApp->dragDropHelper().resetDragAndDrop();
    QTableView::startDrag(supportedActions);
}
