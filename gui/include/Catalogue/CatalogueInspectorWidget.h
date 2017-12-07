#ifndef SCIQLOP_CATALOGUEINSPECTORWIDGET_H
#define SCIQLOP_CATALOGUEINSPECTORWIDGET_H

#include <QWidget>

namespace Ui {
class CatalogueInspectorWidget;
}

class CatalogueInspectorWidget : public QWidget {
    Q_OBJECT

public:
    explicit CatalogueInspectorWidget(QWidget *parent = 0);
    virtual ~CatalogueInspectorWidget();

    /// Enum matching the pages inside the stacked widget
    enum class Page { Empty, CatalogueProperties, EventProperties };

    Page currentPage() const;

    void setEvent(const QString &event);
    void setCatalogue(const QString &catalogue);

public slots:
    void showPage(Page page);

private:
    Ui::CatalogueInspectorWidget *ui;
};

#endif // SCIQLOP_CATALOGUEINSPECTORWIDGET_H
