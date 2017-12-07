#ifndef SCIQLOP_VISUALIZATIONMULTIZONESELECTIONDIALOG_H
#define SCIQLOP_VISUALIZATIONMULTIZONESELECTIONDIALOG_H

#include <Common/spimpl.h>
#include <QDialog>

namespace Ui {
class VisualizationMultiZoneSelectionDialog;
}

class VisualizationSelectionZoneItem;

class VisualizationMultiZoneSelectionDialog : public QDialog {
    Q_OBJECT

public:
    explicit VisualizationMultiZoneSelectionDialog(QWidget *parent = 0);
    ~VisualizationMultiZoneSelectionDialog();

    void setZones(const QVector<VisualizationSelectionZoneItem *> &zones);
    QMap<VisualizationSelectionZoneItem *, bool> selectedZones() const;

private:
    Ui::VisualizationMultiZoneSelectionDialog *ui;

    class VisualizationMultiZoneSelectionDialogPrivate;
    spimpl::unique_impl_ptr<VisualizationMultiZoneSelectionDialogPrivate> impl;
};

#endif // SCIQLOP_VISUALIZATIONMULTIZONESELECTIONDIALOG_H
