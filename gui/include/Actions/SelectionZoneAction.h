#ifndef SCIQLOP_SELECTIONZONEACTION_H
#define SCIQLOP_SELECTIONZONEACTION_H

#include <Common/spimpl.h>

#include <QLoggingCategory>
#include <QObject>

#include <functional>

class VisualizationSelectionZoneItem;

Q_DECLARE_LOGGING_CATEGORY(LOG_SelectionZoneAction)

/**
 * @brief The SelectionZoneAction class represents an action on a selection zone in the
 * visualization.
 *
 * The action is a function that will be executed when the slot execute() is called.
 */
class SelectionZoneAction : public QObject {

    Q_OBJECT

public:
    /// Signature of the function associated to the action
    using ExecuteFunction
        = std::function<void(const QVector<VisualizationSelectionZoneItem *> &item)>;

    using EnableFunction
        = std::function<bool(const QVector<VisualizationSelectionZoneItem *> &item)>;

    /**
     * @param name the name of the action, displayed to the user
     * @param fun the function that will be called when the action is executed
     * @sa execute()
     */
    explicit SelectionZoneAction(const QString &name, ExecuteFunction fun);

    /// Sets the function which determine if the action should be enabled or disabled
    void setEnableFunction(EnableFunction fun);

    /// The name of the action
    QString name() const noexcept;

public slots:
    /// Executes the action
    void execute(const QVector<VisualizationSelectionZoneItem *> &item);

    /// Returns true if the action is enabled
    bool isEnabled(const QVector<VisualizationSelectionZoneItem *> &item);

private:
    class SelectionZoneActionPrivate;
    spimpl::unique_impl_ptr<SelectionZoneActionPrivate> impl;
};

#endif // SCIQLOP_SELECTIONZONEACTION_H
