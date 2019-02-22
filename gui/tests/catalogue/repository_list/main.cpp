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

#include <Catalogue2/repositoriestreeview.h>


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
    Q_INIT_RESOURCE(sqpguiresources);
    QGuiApplication::setAttribute(Qt::AA_EnableHighDpiScaling);

    SqpApplication a { argc, argv };
    RepositoriesTreeView w;
    sqpApp->catalogueController().add("test");
    sqpApp->catalogueController().add("stuff");
    sqpApp->catalogueController().add("default");
    sqpApp->catalogueController().add("new catalogue", "default");
    sqpApp->catalogueController().add("new catalogue2", "default");
    w.show();
    w.refresh();
    return a.exec();
}
