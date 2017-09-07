#include <Common/StringUtils.h>

#include <QObject>
#include <QtTest>

class TestStringUtils : public QObject {
    Q_OBJECT

private slots:
    void testUniqueName_data();
    void testUniqueName();
};

void TestStringUtils::testUniqueName_data()
{
    // ////////////// //
    // Test structure //
    // ////////////// //

    QTest::addColumn<QString>("defaultName");
    QTest::addColumn<std::vector<QString> >("forbiddenNames");
    QTest::addColumn<QString>("expectedName");

    // ////////// //
    // Test cases //
    // ////////// //

    QTest::newRow("uniqueName") << "FGM" << std::vector<QString>{"FGM2"} << "FGM";
    QTest::newRow("uniqueName2") << "FGM2" << std::vector<QString>{"FGM", "FGM1", "FGM2"} << "FGM3";
    QTest::newRow("uniqueName3") << "FGM1" << std::vector<QString>{"FGM1"} << "FGM";
    QTest::newRow("uniqueName4") << "FGM" << std::vector<QString>{"FGM"} << "FGM1";
    QTest::newRow("uniqueName5") << "FGM" << std::vector<QString>{"FGM", "FGM1", "FGM3"} << "FGM2";
    QTest::newRow("uniqueName6") << "FGM" << std::vector<QString>{"A", "B", "C"} << "FGM";
    QTest::newRow("uniqueName7") << "FGM" << std::vector<QString>{"fGm", "FGm1", "Fgm2"} << "FGM3";
    QTest::newRow("uniqueName8") << "" << std::vector<QString>{"A", "B", "C"} << "1";
    QTest::newRow("uniqueName9") << "24" << std::vector<QString>{"A", "B", "C"} << "1";
}

void TestStringUtils::testUniqueName()
{
    QFETCH(QString, defaultName);
    QFETCH(std::vector<QString>, forbiddenNames);
    QFETCH(QString, expectedName);

    auto result = StringUtils::uniqueName(defaultName, forbiddenNames);
    QCOMPARE(result, expectedName);
}

QTEST_MAIN(TestStringUtils)
#include "TestStringUtils.moc"
