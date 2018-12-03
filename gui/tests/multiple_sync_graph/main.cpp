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

#include <Visualization/VisualizationZoneWidget.h>
#include <Visualization/VisualizationGraphWidget.h>
#include <TestProviders.h>
#include <GUITestUtils.h>

template <int GraphCount=2>
std::tuple< std::unique_ptr<VisualizationZoneWidget>,
            std::vector<std::shared_ptr<Variable>>,
            std::vector<VisualizationGraphWidget*>,
            DateTimeRange>
build_multi_graph_test()
{
    auto w = std::make_unique<VisualizationZoneWidget>();
    auto provider = std::make_shared<SimpleRange<10> >();
    auto range = DateTimeRange::fromDateTime(QDate(2018, 8, 7), QTime(14, 00), QDate(2018, 8, 7),QTime(16, 00));
    std::vector<std::shared_ptr<Variable>> variables;
    std::vector<VisualizationGraphWidget*> graphs;
    for(auto i=0;i<GraphCount;i++)
    {
        auto var = static_cast<SqpApplication *>(qApp)->variableController().createVariable(
                    QString("V%1").arg(i), {{"", "scalar"}}, provider, range);
        auto graph = new VisualizationGraphWidget();
        graph->addVariable(var, range);
        while (!isReady(var))
            QCoreApplication::processEvents();
        variables.push_back(var);
        graphs.push_back(graph);
        w->addGraph(graph);
    }
    return {std::move(w), variables, graphs, range};
}


class A_MultipleSyncGraphs : public QObject {
    Q_OBJECT
public:
    explicit A_MultipleSyncGraphs(QObject *parent = Q_NULLPTR) : QObject(parent) {}

private slots:
    void scrolls_left_with_mouse()
    {
        auto [w, variables, graphs, range] = build_multi_graph_test<3>();
        auto var   = variables.front();
        auto graph = graphs.front();
        QVERIFY(prepare_gui_test(w.get()));
        for (auto i = 0; i < 100; i++) {
            scroll_graph(graph, -200);
            waitForVar(var);
        }
        auto r = variables.back()->range();

        /*
         * Scrolling to the left implies going back in time
         * Scroll only implies keeping the same delta T -> shit only transformation
        */
        QVERIFY(r.m_TEnd < range.m_TEnd);
        QVERIFY(SciQLop::numeric::almost_equal<double>(r.delta(),range.delta(),1));
    }

    void scrolls_right_with_mouse()
    {
        auto [w, variables, graphs, range] = build_multi_graph_test<3>();
        auto var   = variables.front();
        auto graph = graphs.front();
        QVERIFY(prepare_gui_test(w.get()));
        for (auto i = 0; i < 100; i++) {
            scroll_graph(graph, 200);
            waitForVar(var);
        }
        auto r = variables.back()->range();

        /*
         * Scrolling to the right implies going forward in time
         * Scroll only implies keeping the same delta T -> shit only transformation
        */
        QVERIFY(r.m_TEnd > range.m_TEnd);
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
    QTEST_DISABLE_KEYPAD_NAVIGATION;
    QTEST_ADD_GPU_BLACKLIST_SUPPORT;
    A_MultipleSyncGraphs tc;
    QTEST_SET_MAIN_SOURCE_PATH;
    return QTest::qExec(&tc, argc, argv);
}

#include "main.moc"
