#include <QtTest>
#include <QObject>
#include <QString>
#include <QScreen>
#include <QMainWindow>


#include <SqpApplication.h>
#include <Variable/VariableController2.h>

#include <Visualization/VisualizationGraphWidget.h>
#include <TestProviders.h>


class A_SimpleGraph : public QObject {
    Q_OBJECT
public:
    A_SimpleGraph(QObject* parent=Q_NULLPTR)
        :QObject(parent)
    {

    }

private slots:
    void scrolls_with_mouse_wheel()
    {
        VisualizationGraphWidget w{Q_NULLPTR};
        auto provider = std::make_shared<SimpleRange<10>>();
        auto range = DateTimeRange::fromDateTime(QDate(2018,8,7),QTime(14,00),
                                              QDate(2018,8,7),QTime(16,00));
        auto var = static_cast<SqpApplication*>(qApp)->variableController().createVariable("V1", {{"","scalar"}}, provider, range);
        w.addVariable(var, range);
        while(!static_cast<SqpApplication*>(qApp)->variableController().isReady(var))QCoreApplication::processEvents();
    }
};

QT_BEGIN_NAMESPACE
QTEST_ADD_GPU_BLACKLIST_SUPPORT_DEFS
QT_END_NAMESPACE \
int main(int argc, char *argv[])
{
    SqpApplication app{argc, argv};
    app.setAttribute(Qt::AA_Use96Dpi, true);
    QTEST_DISABLE_KEYPAD_NAVIGATION
    QTEST_ADD_GPU_BLACKLIST_SUPPORT
    A_SimpleGraph tc;
    QTEST_SET_MAIN_SOURCE_PATH
    return QTest::qExec(&tc, argc, argv);
}

#include "main.moc"
