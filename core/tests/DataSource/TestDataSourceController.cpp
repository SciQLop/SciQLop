#include <DataSource/DataSourceController.h>
#include <DataSource/DataSourceItem.h>

#include <QObject>
#include <QtTest>

#include <memory>

class TestDataSourceController : public QObject {
    Q_OBJECT
private slots:
    void testRegisterDataSource();
    void testSetDataSourceItem();
};

void TestDataSourceController::testRegisterDataSource()
{
    DataSourceController dataSourceController{};

    auto uid = dataSourceController.registerDataSource(QStringLiteral("Source1"));
    QVERIFY(!uid.isNull());
}

void TestDataSourceController::testSetDataSourceItem()
{
    DataSourceController dataSourceController{};

    // Spy to test controllers' signals
    QSignalSpy signalSpy{&dataSourceController, SIGNAL(dataSourceItemSet(DataSourceItem *))};

    // Create a data source item
    auto source1Name = QStringLiteral("Source1");
    auto source1Item = std::make_unique<DataSourceItem>(DataSourceItemType::PRODUCT, source1Name);

    // Add data source item to the controller and check that a signal has been emitted after setting
    // data source item in the controller
    auto source1Uid = dataSourceController.registerDataSource(source1Name);
    dataSourceController.setDataSourceItem(source1Uid, std::move(source1Item));
    QCOMPARE(signalSpy.count(), 1);

    // Try to a data source item with an unregistered uid and check that no signal has been emitted
    auto unregisteredUid = QUuid::createUuid();
    dataSourceController.setDataSourceItem(
        unregisteredUid, std::make_unique<DataSourceItem>(DataSourceItemType::PRODUCT));
    QCOMPARE(signalSpy.count(), 1);
}

QTEST_MAIN(TestDataSourceController)
#include "TestDataSourceController.moc"
