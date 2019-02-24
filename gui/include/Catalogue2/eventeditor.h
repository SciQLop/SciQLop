#ifndef EVENTEDITOR_H
#define EVENTEDITOR_H

#include <QWidget>
#include <Catalogue/CatalogueController.h>

namespace Ui {
class EventEditor;
}

class EventEditor : public QWidget
{
    Q_OBJECT
    enum class mode{
        editable = true,
        readonly = false
    };

public:
    explicit EventEditor(QWidget *parent = nullptr);
    ~EventEditor();

public slots:
    void setEvent(const CatalogueController::Event_ptr& event);
    void setProduct(const CatalogueController::Product_t& product, const CatalogueController::Event_ptr& event);

private:
    void _setEventName(const CatalogueController::Event_ptr& event, mode is_editable=mode::editable);
    void _setTags(const CatalogueController::Event_ptr& event,mode is_editable=mode::editable);
    void _setProducts(const CatalogueController::Event_ptr& event,mode is_editable=mode::editable);
    void _setProducts(const CatalogueController::Product_t& product,mode is_editable=mode::editable);
    void _setDates(double startDate, double stopDate, mode is_editable=mode::editable);
    void _setDates(std::optional<double> startDate, std::optional<double> stopDate, mode is_editable=mode::editable);
    Ui::EventEditor *ui;
};

#endif // EVENTEDITOR_H
