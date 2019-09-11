#include <QMainWindow>
#include <QObject>
#include <QScreen>
#include <QString>
#include <QWheelEvent>
#include <QtTest>
#include <cstdlib>


#include <cpp_utils.hpp>
#include <SqpApplication.h>

#include <GUITestUtils.h>

#include <Catalogue/CatalogueController.h>
#include <Catalogue2/browser.h>

template <int EventsCount = 1000>
auto build_CatalogueBrowser_test()
{
    sqpApp->catalogueController().add("test");
    sqpApp->catalogueController().add("stuff");
    sqpApp->catalogueController().add("default");
    sqpApp->catalogueController().add("new catalogue", "default");
    auto catalogue = sqpApp->catalogueController().add("new catalogue2", "default");
    for (auto _ : std::array<char, EventsCount>())
    {
        (void)_;
        static int i = 0;
        auto event = CatalogueController::make_event_ptr();
        event->name = std::string("Event ") + std::to_string(i++);
        event->tags = { "tag1", "tag2" };
        event->products = { CatalogueController::Event_t::Product_t {
                                std::string("Product2") + std::to_string(rand() % 30),
                                static_cast<double>(1532357932 + rand() % 100),
                                static_cast<double>(1532358932 + rand() % 100) },
            CatalogueController::Event_t::Product_t {
                std::string("Product2") + std::to_string(rand() % 30),
                static_cast<double>(1532357932 + rand() % 200),
                static_cast<double>(1532358932 + rand() % 200) },
            CatalogueController::Event_t::Product_t {
                std::string("Product2") + std::to_string(rand() % 30),
                static_cast<double>(1532357932 + rand() % 70),
                static_cast<double>(1532358932 + rand() % 70) } };
        catalogue->add(event);
    }
    return std::make_unique<CataloguesBrowser>();
}

class A_CatalogueBrowser : public QObject
{
    Q_OBJECT
public:
    explicit A_CatalogueBrowser(QObject* parent = Q_NULLPTR) : QObject(parent) {}

private slots:
    void can_sort_events()
    {
        auto w = build_CatalogueBrowser_test();
        QVERIFY(prepare_gui_test(w.get()));
        // GET_CHILD_WIDGET_FOR_GUI_TESTS((*w.get()),,,)
        for (int i = 0; i < 1000000; i++)
        {
            QThread::usleep(100);
            QCoreApplication::processEvents();
        }
    }
};

QT_BEGIN_NAMESPACE
QTEST_ADD_GPU_BLACKLIST_SUPPORT_DEFS
QT_END_NAMESPACE
int main(int argc, char* argv[])
{
    Q_INIT_RESOURCE(sqpguiresources);

    SqpApplication app { argc, argv };
    app.setAttribute(Qt::AA_Use96Dpi, true);
    QTEST_DISABLE_KEYPAD_NAVIGATION;
    QTEST_ADD_GPU_BLACKLIST_SUPPORT;
    A_CatalogueBrowser tc;
    QTEST_SET_MAIN_SOURCE_PATH;
    return QTest::qExec(&tc, argc, argv);
}

#include "main.moc"
