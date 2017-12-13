#ifndef SCIQLOP_CATALOGUEINSPECTORWIDGET_H
#define SCIQLOP_CATALOGUEINSPECTORWIDGET_H

#include <Common/spimpl.h>
#include <QWidget>
#include <memory>

namespace Ui {
class CatalogueInspectorWidget;
}

class DBCatalogue;
class DBEvent;

class CatalogueInspectorWidget : public QWidget {
    Q_OBJECT

signals:
    void catalogueUpdated(const std::shared_ptr<DBCatalogue> &catalogue);
    void eventUpdated(const std::shared_ptr<DBEvent> &event);

public:
    explicit CatalogueInspectorWidget(QWidget *parent = 0);
    virtual ~CatalogueInspectorWidget();

    /// Enum matching the pages inside the stacked widget
    enum class Page { Empty, CatalogueProperties, EventProperties };

    Page currentPage() const;

    void setEvent(const std::shared_ptr<DBEvent> &event);
    void setCatalogue(const std::shared_ptr<DBCatalogue> &catalogue);

public slots:
    void showPage(Page page);

private:
    Ui::CatalogueInspectorWidget *ui;

    class CatalogueInspectorWidgetPrivate;
    spimpl::unique_impl_ptr<CatalogueInspectorWidgetPrivate> impl;
};

#endif // SCIQLOP_CATALOGUEINSPECTORWIDGET_H
