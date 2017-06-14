#ifndef SCIQLOP_DATASOURCEWIDGET_H
#define SCIQLOP_DATASOURCEWIDGET_H

#include <QWidget>

namespace Ui {
class DataSourceWidget;
} // Ui

class DataSourceItem;

/**
 * @brief The DataSourceWidget handles the graphical representation (as a tree) of the data sources
 * attached to SciQlop.
 */
class DataSourceWidget : public QWidget {
    Q_OBJECT

public:
    explicit DataSourceWidget(QWidget *parent = 0);

public slots:
    /**
     * Adds a data source. An item associated to the data source is created and then added to the
     * representation tree
     * @param dataSource the data source to add. The pointer has to be not null
     */
    void addDataSource(DataSourceItem *dataSource) noexcept;

private:
    Ui::DataSourceWidget *ui;
};

#endif // SCIQLOP_DATASOURCEWIDGET_H
