#include "Visualization/ColorScaleEditor.h"

#include "ui_ColorScaleEditor.h"

ColorScaleEditor::ColorScaleEditor(QWidget *parent) : QDialog{parent}, ui{new Ui::ColorScaleEditor}
{
    ui->setupUi(this);
}

ColorScaleEditor::~ColorScaleEditor() noexcept
{
    delete ui;
}
