#include "TimeWidget/TimeWidget.h"
#include "ui_TimeWidget.h"

TimeWidget::TimeWidget(QWidget *parent) : QWidget{parent}, ui{new Ui::TimeWidget}
{
    ui->setupUi(this);
}

TimeWidget::~TimeWidget()
{
    delete ui;
}
