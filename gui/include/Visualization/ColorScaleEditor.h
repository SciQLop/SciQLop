#ifndef SCIQLOP_COLORSCALEEDITOR_H
#define SCIQLOP_COLORSCALEEDITOR_H

#include <QDialog>

namespace Ui {
class ColorScaleEditor;
} // Ui

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
};

#endif // SCIQLOP_COLORSCALEEDITOR_H
