#ifndef SCIQLOP_DATASOURCEWIDGET_H
#define SCIQLOP_DATASOURCEWIDGET_H

#include <Common/spimpl.h>

#include <QWidget>

class DataSourceItem;

/**
 * @brief The DataSourceWidget handles the graphical representation (as a tree) of the data sources
 * attached to SciQlop.
 */
class DataSourceWidget : public QWidget {
    Q_OBJECT

public:
    explicit DataSourceWidget(QWidget *parent = 0);

private:
    class DataSourceWidgetPrivate;
    spimpl::unique_impl_ptr<DataSourceWidgetPrivate> impl;
};

#endif // SCIQLOP_DATASOURCEWIDGET_H
