#include <QtTest>
#include <QObject>
#include <QString>
#include <QScreen>
#include <QMainWindow>
#include <QWheelEvent>

#include <qcustomplot.h>

#include <SqpApplication.h>
#include <Variable/VariableController2.h>

#include <Visualization/VisualizationGraphWidget.h>
#include <TestProviders.h>
#include <GUITestUtils.h>

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
        VisualizationGraphWidget w;
        PREPARE_GUI_TEST(w);
        auto provider = std::make_shared<SimpleRange<10>>();
        auto range = DateTimeRange::fromDateTime(QDate(2018,8,7),QTime(14,00),
                                                 QDate(2018,8,7),QTime(16,00));
        auto var = static_cast<SqpApplication*>(qApp)->variableController().createVariable("V1", {{"","scalar"}}, provider, range);
        while(!static_cast<SqpApplication*>(qApp)->variableController().isReady(var))QCoreApplication::processEvents();
        w.addVariable(var, range);
        GET_CHILD_WIDGET_FOR_GUI_TESTS(w,plot,QCustomPlot,"widget");
        auto cent = center(static_cast<QWidget*>(plot));
        for(auto i=0;i<10;i++)
        {
            QTest::mousePress(plot, Qt::LeftButton, Qt::NoModifier, cent, 10);
            QTest::mouseMove(plot, {cent.x()+100,cent.y()},10);
            QTest::mouseRelease(plot,Qt::LeftButton);
        }
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
