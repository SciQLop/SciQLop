#ifndef SCIQLOP_COLORSCALEEDITOR_H
#define SCIQLOP_COLORSCALEEDITOR_H

#include <QButtonGroup>
#include <QDialog>

namespace Ui {
class ColorScaleEditor;
} // Ui

class SqpColorScale;
class QCPColorScale;

/**
 * @brief The ColorScaleEditor class represents the widget to set properties of color scale's graphs
 */
class ColorScaleEditor : public QDialog {
    Q_OBJECT

public:
    explicit ColorScaleEditor(SqpColorScale &scale, QWidget *parent = 0);
    virtual ~ColorScaleEditor() noexcept;

private:
    /// Fills the editor fields from color scale data
    void loadScale();
    /// Updates the color scale from editor fields
    void saveScale();

    Ui::ColorScaleEditor *ui;
    QButtonGroup *m_ThresholdGroup;
    /// Scale in editing
    /// @remarks reference must remain valid throughout the existence of the ColorScaleEditor
    /// instance
    SqpColorScale &m_Scale;
    /// Scale shown as preview
    QCPColorScale *m_PreviewScale;

private slots:
    /// @sa QDialog::accept()
    void accept() override;

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
