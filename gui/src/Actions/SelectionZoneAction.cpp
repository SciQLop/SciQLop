#include <Actions/SelectionZoneAction.h>
#include <Visualization/VisualizationSelectionZoneItem.h>

Q_LOGGING_CATEGORY(LOG_SelectionZoneAction, "SelectionZoneAction")

struct SelectionZoneAction::SelectionZoneActionPrivate {
    explicit SelectionZoneActionPrivate(const QString &name,
                                        SelectionZoneAction::ExecuteFunction fun)
            : m_Name{name}, m_Fun{std::move(fun)}
    {
    }

    QString m_Name;
    QKeySequence m_DisplayedShortcut;
    SelectionZoneAction::ExecuteFunction m_Fun;
    SelectionZoneAction::EnableFunction m_EnableFun = [](auto zones) { return true; };
};

SelectionZoneAction::SelectionZoneAction(const QString &name, ExecuteFunction fun)
        : impl{spimpl::make_unique_impl<SelectionZoneActionPrivate>(name, std::move(fun))}
{
}

void SelectionZoneAction::setEnableFunction(EnableFunction fun)
{
    impl->m_EnableFun = std::move(fun);
}

void SelectionZoneAction::setDisplayedShortcut(const QKeySequence &shortcut)
{
    impl->m_DisplayedShortcut = shortcut;
}

QKeySequence SelectionZoneAction::displayedShortcut() const
{
    return impl->m_DisplayedShortcut;
}

QString SelectionZoneAction::name() const noexcept
{
    return impl->m_Name;
}

void SelectionZoneAction::execute(const QVector<VisualizationSelectionZoneItem *> &item)
{
    impl->m_Fun(item);
}

bool SelectionZoneAction::isEnabled(const QVector<VisualizationSelectionZoneItem *> &item)
{
    return impl->m_EnableFun(item);
}
