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
    SelectionZoneAction::ExecuteFunction m_Fun;
};

SelectionZoneAction::SelectionZoneAction(const QString &name, ExecuteFunction fun)
        : impl{spimpl::make_unique_impl<SelectionZoneActionPrivate>(name, std::move(fun))}
{
}

QString SelectionZoneAction::name() const noexcept
{
    return impl->m_Name;
}

void SelectionZoneAction::execute(const QVector<VisualizationSelectionZoneItem *> &item)
{
    impl->m_Fun(item);
}
