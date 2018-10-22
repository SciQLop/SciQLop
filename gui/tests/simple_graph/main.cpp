#include <QtTest>
#include <QObject>
#include <QString>
#include <QScreen>
#include <QMainWindow>
#include <QWheelEvent>

#include <qcustomplot.h>

#include <SqpApplication.h>
#include <Variable/VariableController2.h>
#include <Common/cpp_utils.h>

#include <Visualization/VisualizationGraphWidget.h>
#include <TestProviders.h>
#include <GUITestUtils.h>


ALIAS_TEMPLATE_FUNCTION(isReady, static_cast<SqpApplication *>(qApp)->variableController().isReady)

#define A_SIMPLE_GRAPH_FIXTURE \
        VisualizationGraphWidget w;\
        PREPARE_GUI_TEST(w);\
        auto provider = std::make_shared<SimpleRange<10> >();\
        auto range = DateTimeRange::fromDateTime(QDate(2018, 8, 7), QTime(14, 00), QDate(2018, 8, 7),\
                                                 QTime(16, 00));\
        auto var = static_cast<SqpApplication *>(qApp)->variableController().createVariable(\
            "V1", {{"", "scalar"}}, provider, range);\
        while (!isReady(var))\
            QCoreApplication::processEvents();\
        w.addVariable(var, range);\
        GET_CHILD_WIDGET_FOR_GUI_TESTS(w, plot, QCustomPlot, "widget");\
        auto cent = center(plot);\


class A_SimpleGraph : public QObject {
    Q_OBJECT
public:
    explicit A_SimpleGraph(QObject *parent = Q_NULLPTR) : QObject(parent) {}

private slots:
    void scrolls_with_mouse()
    {
        A_SIMPLE_GRAPH_FIXTURE

        for (auto i = 0; i < 10; i++) {
            QTest::mousePress(plot, Qt::LeftButton, Qt::NoModifier, cent, 5);
            mouseMove(plot, {cent.x() + 200, cent.y()}, Qt::LeftButton);
            QTest::mouseRelease(plot, Qt::LeftButton);
            while (!isReady(var))
                QCoreApplication::processEvents();
            /*
             * Just for visual inspection while running tests
             */
            plot->rescaleAxes();
            plot->replot();
            QCoreApplication::processEvents();
        }
        while (!isReady(var))
            QCoreApplication::processEvents();
        auto r = var->range();
        QVERIFY(r.m_TEnd < range.m_TEnd);
        // this fails :(
        QVERIFY(SciQLop::numeric::almost_equal<double>(r.delta(),range.delta(),1));
    }
};

QT_BEGIN_NAMESPACE
QTEST_ADD_GPU_BLACKLIST_SUPPORT_DEFS
QT_END_NAMESPACE
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
