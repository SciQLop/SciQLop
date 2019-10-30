#ifndef SCIQLOP_DATASOURCEWIDGET_H
#define SCIQLOP_DATASOURCEWIDGET_H

#include <QWidget>

#include <QSortFilterProxyModel>

namespace Ui
{
class DataSourceWidget;
} // Ui

class DataSourceItem;

/**
 * @brief The DataSourceWidget handles the graphical representation (as a tree) of the data sources
 * attached to SciQlop.
 */
class DataSourceWidget : public QWidget
{
    Q_OBJECT

public:
    explicit DataSourceWidget(QWidget* parent = 0);
    virtual ~DataSourceWidget() noexcept;

private:
    void updateTreeWidget() noexcept;

    Ui::DataSourceWidget* ui;
    QSortFilterProxyModel m_model_proxy;

};

#endif // SCIQLOP_DATASOURCEWIDGET_H
