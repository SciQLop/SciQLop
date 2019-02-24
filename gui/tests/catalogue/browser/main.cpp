#include <QMainWindow>
#include <QObject>
#include <QScreen>
#include <QString>
#include <QWheelEvent>
#include <QtTest>


#include <Common/cpp_utils.h>
#include <SqpApplication.h>

#include <GUITestUtils.h>
#include <TestProviders.h>

#include <Catalogue/CatalogueController.h>
#include <Catalogue2/browser.h>


class A_CatalogueBrowser : public QObject
{
    Q_OBJECT
public:
    explicit A_CatalogueBrowser(QObject* parent = Q_NULLPTR) : QObject(parent) {}

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
    Q_INIT_RESOURCE(sqpguiresources);
    QGuiApplication::setAttribute(Qt::AA_EnableHighDpiScaling);

    SqpApplication a { argc, argv };
    Browser w;
    sqpApp->catalogueController().add("test");
    sqpApp->catalogueController().add("stuff");
    sqpApp->catalogueController().add("default");
    sqpApp->catalogueController().add("new catalogue", "default");
    auto catalogue = sqpApp->catalogueController().add("new catalogue2", "default");
    for (auto _ : std::array<char, 1000>())
    {
        static int i = 0;
        auto event = CatalogueController::make_event_ptr();
        event->name = std::string("Event ") + std::to_string(i++);
        event->tags = {"tag1", "tag2"};
        event->products = { CatalogueController::Event_t::Product_t { "Product1", 10., 11. },
            CatalogueController::Event_t::Product_t { "Product2", 11., 12. },
            CatalogueController::Event_t::Product_t { "Product3", 10.2, 11. } };
        catalogue->add(event);
    }
    w.show();
    return a.exec();
}
