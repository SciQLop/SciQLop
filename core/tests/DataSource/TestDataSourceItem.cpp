#include <DataSource/DataSourceItem.h>

#include <QObject>
#include <QtTest>

#include <iostream>

namespace {

void printItem(std::ostream &out, const DataSourceItem &item, int level = 0)
{
    for (auto i = 0; i < level; ++i) {
        out << "    ";
    }

    out << item.name().toStdString() << "\n";

    for (auto i = 0, count = item.childCount(); i < count; ++i) {
        printItem(out, *item.child(i), level + 1);
    }
}

std::ostream &operator<<(std::ostream &out, const DataSourceItem &item)
{
    printItem(out, item, 0);
    return out;
}

} // namespace

Q_DECLARE_METATYPE(std::shared_ptr<DataSourceItem>)

class TestDataSourceItem : public QObject {
    Q_OBJECT
private slots:
    void testMerge_data();
    void testMerge();
};

void TestDataSourceItem::testMerge_data()
{
    QTest::addColumn<std::shared_ptr<DataSourceItem> >("source");
    QTest::addColumn<std::shared_ptr<DataSourceItem> >("dest");
    QTest::addColumn<std::shared_ptr<DataSourceItem> >("expectedResult");

    /// @todo ALX: adds test cases
}

void TestDataSourceItem::testMerge()
{
    QFETCH(std::shared_ptr<DataSourceItem>, source);
    QFETCH(std::shared_ptr<DataSourceItem>, dest);
    QFETCH(std::shared_ptr<DataSourceItem>, expectedResult);

    // Uncomment to print trees
    //    std::cout << "source: \n" << *source << "\n";
    //    std::cout << "dest: \n" << *dest << "\n";

    // Merges source in dest (not taking source root)
    for (auto i = 0, count = source->childCount(); i < count; ++i) {
        dest->merge(*source->child(i));
    }

    // Uncomment to print trees
    //    std::cout << "dest after merge: \n" << *dest << "\n";

    // Checks merge result
    QVERIFY(*dest == *expectedResult);
}

QTEST_MAIN(TestDataSourceItem)
#include "TestDataSourceItem.moc"
