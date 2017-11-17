#ifndef SCIQLOP_COLORSCALEEDITOR_H
#define SCIQLOP_COLORSCALEEDITOR_H

#include <QButtonGroup>
#include <QDialog>

namespace Ui {
class ColorScaleEditor;
} // Ui

class QCPColorScale;

/**
 * @brief The ColorScaleEditor class represents the widget to set properties of color scale's graphs
 */
class ColorScaleEditor : public QDialog {
    Q_OBJECT

public:
    explicit ColorScaleEditor(QWidget *parent = 0);
    virtual ~ColorScaleEditor() noexcept;

private:
    Ui::ColorScaleEditor *ui;
    QButtonGroup *m_ThresholdGroup;
    QCPColorScale *m_PreviewScale; ///< Scale shown as preview

private slots:
    /// Slot called when max threshold value changes
    void onMaxChanged();
    /// Slot called when min threshold value changes
    void onMinChanged();
    /// Slot called when the threshold mode (auto or manual) changes
    void onThresholdChanged(bool checked);

    /// Slot called when a property of the color scale changed
    void updatePreview();
};

#endif // SCIQLOP_COLORSCALEEDITOR_H
