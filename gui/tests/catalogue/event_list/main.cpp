#include <QMainWindow>
#include <QObject>
#include <QScreen>
#include <QString>
#include <QWheelEvent>
#include <QtTest>

#include <QTreeView>


#include <Common/cpp_utils.h>
#include <SqpApplication.h>

#include <GUITestUtils.h>
#include <TestProviders.h>

//#include <Catalogue/CatalogueEventsWidget.h>

#include <Catalogue2/eventstreeview.h>


class An_EventList : public QObject
{
    Q_OBJECT
public:
    explicit An_EventList(QObject* parent = Q_NULLPTR) : QObject(parent) {}

private slots:
};

// QT_BEGIN_NAMESPACE
// QTEST_ADD_GPU_BLACKLIST_SUPPORT_DEFS
// QT_END_NAMESPACE
// int main(int argc, char* argv[])
//{
//    SqpApplication app { argc, argv };
//    app.setAttribute(Qt::AA_Use96Dpi, true);
//    QTEST_DISABLE_KEYPAD_NAVIGATION;
//    QTEST_ADD_GPU_BLACKLIST_SUPPORT;
//    An_EventList tc;
//    QTEST_SET_MAIN_SOURCE_PATH;
//    return QTest::qExec(&tc, argc, argv);
//}

#include "main.moc"


int main(int argc, char* argv[])
{
    QGuiApplication::setAttribute(Qt::AA_EnableHighDpiScaling);

    SqpApplication a { argc, argv };
    EventsTreeView w;
    std::vector<CatalogueController::Event_ptr> events;
    for (auto _ : std::array<char, 10>())
    {
        static int i = 0;
        auto event = CatalogueController::make_event_ptr();
        event->name = std::string("Event ") + std::to_string(i++);
        event->products = { CatalogueController::Event_t::Product_t { "Product1", 10., 11. },
            CatalogueController::Event_t::Product_t { "Product2", 11., 12. },
            CatalogueController::Event_t::Product_t { "Product3", 10.2, 11. } };
        events.push_back(event);
    }
    w.setEvents(events);
    w.show();
    return a.exec();
}
