#include "Settings/SqpSettingsDialog.h"
#include "ui_SqpSettingsDialog.h"

namespace {

/**
 * Performs a bind operation on widgets that can be binded to SciQlop settings
 * @param widgets
 * @param bind the bind operation
 * @sa ISqpSettingsBindable
 */
template <typename BindMethod>
void processBind(const QStackedWidget &widgets, BindMethod bind)
{
    auto count = widgets.count();
    for (auto i = 0; i < count; ++i) {
        // Performs operation if widget is an ISqpSettingsBindable
        if (auto sqpSettingsWidget = dynamic_cast<ISqpSettingsBindable *>(widgets.widget(i))) {
            bind(*sqpSettingsWidget);
        }
    }
}

} // namespace

SqpSettingsDialog::SqpSettingsDialog(QWidget *parent)
        : QDialog{parent}, ui{new Ui::SqpSettingsDialog}
{
    ui->setupUi(this);

    // Connection to change the current page to the selection of an entry in the list
    connect(ui->listWidget, &QListWidget::currentRowChanged, ui->stackedWidget,
            &QStackedWidget::setCurrentIndex);
}

SqpSettingsDialog::~SqpSettingsDialog() noexcept
{
    delete ui;
}

void SqpSettingsDialog::loadSettings()
{
    // Performs load on all widgets that can be binded to SciQlop settings
    processBind(*ui->stackedWidget,
                [](ISqpSettingsBindable &bindable) { bindable.loadSettings(); });
}

void SqpSettingsDialog::saveSettings() const
{
    // Performs save on all widgets that can be binded to SciQlop settings
    processBind(*ui->stackedWidget,
                [](ISqpSettingsBindable &bindable) { bindable.saveSettings(); });
}

void SqpSettingsDialog::registerWidget(const QString &name, QWidget *widget) noexcept
{
    auto newItem = new QListWidgetItem{ui->listWidget};
    newItem->setText(name);

    ui->stackedWidget->addWidget(widget);

    // Selects widget if it's the first in the dialog
    if (ui->listWidget->count() == 1) {
        ui->listWidget->setCurrentItem(newItem);
    }
}
