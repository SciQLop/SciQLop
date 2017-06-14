#include "Visualization/VisualizationGraphWidget.h"
#include "ui_VisualizationGraphWidget.h"

#include <Variable/Variable.h>

#include <unordered_map>

struct VisualizationGraphWidget::VisualizationGraphWidgetPrivate {

    // 1 variable -> n qcpplot
    std::unordered_map<std::shared_ptr<Variable>, std::unique_ptr<QCPAbstractPlottable> >
        m_VariableToPlotMap;
};

VisualizationGraphWidget::VisualizationGraphWidget(QWidget *parent)
        : QWidget(parent),
          ui(new Ui::VisualizationGraphWidget),
          impl{spimpl::make_unique_impl<VisualizationGraphWidgetPrivate>()}
{
    ui->setupUi(this);
}

VisualizationGraphWidget::~VisualizationGraphWidget()
{
    delete ui;
}

void VisualizationGraphWidget::addVariable(std::shared_ptr<Variable> variable)
{
    // todo: first check is variable contains data then check how many plot have to be created
}

void VisualizationGraphWidget::accept(IVisualizationWidget *visitor)
{
    // TODO: manage the visitor
}

void VisualizationGraphWidget::close()
{
    // The main view cannot be directly closed.
    return;
}

QString VisualizationGraphWidget::name() const
{
    return QStringLiteral("MainView");
}
