#include "Catalogue2/eventeditor.h"
#include "ui_eventeditor.h"
#include <Common/DateUtils.h>
#include <containers/algorithms.hpp>

EventEditor::EventEditor(QWidget* parent) : QWidget(parent), ui(new Ui::EventEditor)
{
    ui->setupUi(this);
}

EventEditor::~EventEditor()
{
    delete ui;
}

void EventEditor::setEvent(const CatalogueController::Event_ptr& event)
{
    _setEventName(event, mode::editable);
    _setTags(event, mode::readonly);
    _setProducts(event, mode::readonly);
    _setDates(event->startTime(), event->stopTime(), mode::readonly);
}

void EventEditor::setProduct(
    const CatalogueController::Product_t& product, const CatalogueController::Event_ptr& event)
{
    _setEventName(event, mode::readonly);
    _setTags(event, mode::readonly);
    _setDates(product.startTime, product.stopTime, mode::editable);
    _setProducts(product, mode::readonly);
}

void EventEditor::_setEventName(const CatalogueController::Event_ptr& event, mode is_editable)
{
    this->ui->EventName->setText(QString::fromStdString(event->name));
    this->ui->EventName->setEnabled(bool(is_editable));
}

void EventEditor::_setTags(const CatalogueController::Event_ptr& event, mode is_editable)
{
    this->ui->Tags->setText(QString::fromStdString(cpp_utils::containers::join(event->tags, ',')));
    this->ui->Tags->setEnabled(bool(is_editable));
}

void EventEditor::_setProducts(const CatalogueController::Event_ptr& event, mode is_editable)
{
    QStringList products;
    std::transform(std::cbegin(event->products),std::cend(event->products),std::begin(products),[](const auto& product) { return QString::fromStdString(product.name); });
    this->ui->Products->setText(cpp_utils::containers::join(products, QString(", ")));
    this->ui->Products->setEnabled(bool(is_editable));
}

void EventEditor::_setProducts(const CatalogueController::Product_t& product, mode is_editable)
{
    this->ui->Products->setText(QString::fromStdString(product.name));
    this->ui->Products->setEnabled(bool(is_editable));
}

void EventEditor::_setDates(double startDate, double stopDate, mode is_editable)
{
    this->ui->StartTime->setDateTime(DateUtils::dateTime(startDate));
    this->ui->StopTime->setDateTime(DateUtils::dateTime(stopDate));
    this->ui->StartTime->setEnabled(bool(is_editable));
    this->ui->StopTime->setEnabled(bool(is_editable));
}

void EventEditor::_setDates(
    std::optional<double> startDate, std::optional<double> stopDate, mode is_editable)
{
    if (startDate && stopDate)
        _setDates(*startDate, *stopDate, is_editable);
    else
        _setDates(0., 0., is_editable);
}
