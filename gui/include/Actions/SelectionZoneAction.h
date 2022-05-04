#ifndef SCIQLOP_SELECTIONZONEACTION_H
#define SCIQLOP_SELECTIONZONEACTION_H

#include <Common/spimpl.h>

#include <QLoggingCategory>
#include <QObject>

#include <functional>

#include <VisualizationSelectionZoneItem.h>

//class VisualizationSelectionZoneItem;

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

    /**
     * @param name the name of the action, displayed to the user
     * @param subMenusList the list of sub menus where the action should be inserted
     * @param fun the function that will be called when the action is executed
     * @sa execute()
     */
    explicit SelectionZoneAction(const QStringList &subMenuList, const QString &name,
                                 ExecuteFunction fun);

    /// Sets the function which determine if the action should be enabled or disabled
    void setEnableFunction(EnableFunction fun);

    /// Sets the shortcut displayed by the action.
    /// Note: The shortcut is only displayed and not active because it is not permanently stored
    void setDisplayedShortcut(const QKeySequence &shortcut);
    QKeySequence displayedShortcut() const;

    /// The name of the action
    QString name() const noexcept;

    /// The path in the sub menus, if any
    QStringList subMenuList() const noexcept;

    /// Sets if filtering the action is allowed via a FilteringAction
    void setAllowedFiltering(bool value);

    /// Returns true if filtering the action is allowed via a FilteringAction. By default it is
    /// allowed.
    bool isFilteringAllowed() const;

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
