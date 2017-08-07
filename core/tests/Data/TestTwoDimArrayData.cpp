#include "Data/ArrayData.h"
#include <QObject>
#include <QtTest>

using DataContainer = QVector<QVector<double> >;

class TestTwoDimArrayData : public QObject {
    Q_OBJECT
private slots:
};

QTEST_MAIN(TestTwoDimArrayData)
#include "TestTwoDimArrayData.moc"
