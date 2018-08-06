#include <QtTest>
#include <QObject>


class TestVariableController2 : public QObject

{
    Q_OBJECT
public:
    explicit TestVariableController2(QObject *parent = nullptr) : QObject(parent){}
signals:

private slots:
    void initTestCase(){}
    void cleanupTestCase(){}

    void test1()
    {
        QCOMPARE(1+1, 2);
    }

private:

};


QTEST_MAIN(TestVariableController2)

#include "TestVariableController2.moc"

