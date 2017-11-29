#include <DataSource/DataSourceItem.h>

#include "DataSourceItemBuilder.h"

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

    QTest::newRow("merge (basic case)") << DataSourceItemBuilder{}
                                               .root("A2")
                                               .node("- B2")
                                               .product("-- P2")
                                               .end() // P2
                                               .end() // B2
                                               .end() // A2
                                               .build()
                                        << DataSourceItemBuilder{}
                                               .root("A1")
                                               .node("- B1")
                                               .product("-- P1")
                                               .end() // P1
                                               .end() // B1
                                               .end() // A1
                                               .build()
                                        << DataSourceItemBuilder{}
                                               .root("A1")
                                               .node("- B1")
                                               .product("-- P1")
                                               .end() // P1
                                               .end() // B1
                                               .node("- B2")
                                               .product("-- P2")
                                               .end() // P2
                                               .end() // B2
                                               .end() // A1
                                               .build();

    QTest::newRow("merge (some of the source and destination trees are identical)")
        << DataSourceItemBuilder{}
               .root("A2")
               .node("- B1")
               .node("-- C1")
               .product("--- P2")
               .end() // P2
               .end() // C1
               .node("-- C2")
               .end() // C2
               .end() // B1
               .end() // A2
               .build()
        << DataSourceItemBuilder{}
               .root("A1")
               .node("- B1")
               .node("-- C1")
               .product("--- P1")
               .end() // P1
               .end() // C1
               .end() // B1
               .end() // A1
               .build()
        << DataSourceItemBuilder{}
               .root("A1")
               .node("- B1")
               .node("-- C1")
               .product("--- P1")
               .end() // P1
               .product("--- P2")
               .end() // P2
               .end() // C1
               .node("-- C2")
               .end() // C2
               .end() // B1
               .end() // A1
               .build();

    QTest::newRow("merge (products with the same name and tree are kept)")
        << DataSourceItemBuilder{}
               .root("A2")
               .node("- B1")
               .node("-- C1")
               .product({{"name", "--- P1"}, {"from", "source"}})
               .end() // P1
               .end() // C1
               .end() // B1
               .end() // A2
               .build()
        << DataSourceItemBuilder{}
               .root("A1")
               .node("- B1")
               .node("-- C1")
               .product({{"name", "--- P1"}, {"from", "dest"}})
               .end() // P1
               .end() // C1
               .end() // B1
               .end() // A1
               .build()
        << DataSourceItemBuilder{}
               .root("A1")
               .node("- B1")
               .node("-- C1")
               .product({{"name", "--- P1"}, {"from", "dest"}})
               .end() // P1 (dest)
               .product({{"name", "--- P1"}, {"from", "source"}})
               .end() // P1 (source)
               .end() // C1
               .end() // B1
               .end() // A1
               .build();

    QTest::newRow("merge (for same nodes, metadata of dest node are kept)")
        << DataSourceItemBuilder{}
               .root("A2")
               .node("- B1")
               .node({{"name", "-- C1"}, {"from", "source"}})
               .product("--- P2")
               .end() // P1
               .end() // C1
               .end() // B1
               .end() // A2
               .build()
        << DataSourceItemBuilder{}
               .root("A1")
               .node("- B1")
               .node({{"name", "-- C1"}, {"from", "dest"}})
               .product("--- P1")
               .end() // P1
               .end() // C1
               .end() // B1
               .end() // A1
               .build()
        << DataSourceItemBuilder{}
               .root("A1")
               .node("- B1")
               .node({{"name", "-- C1"}, {"from", "dest"}})
               .product("--- P1")
               .end() // P1
               .product("--- P2")
               .end() // P2
               .end() // C1 (dest)
               .end() // B1
               .end() // A1
               .build();
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
