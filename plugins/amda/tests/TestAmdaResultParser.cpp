#include "AmdaResultParser.h"

#include <QObject>
#include <QtTest>

namespace {

/// Path for the tests
const auto TESTS_RESOURCES_PATH
    = QFileInfo{QString{AMDA_TESTS_RESOURCES_DIR}, "TestAmdaResultParser"}.absoluteFilePath();

QString inputFilePath(const QString &inputFileName)
{
    return QFileInfo{TESTS_RESOURCES_PATH, inputFileName}.absoluteFilePath();
}

} // namespace

class TestAmdaResultParser : public QObject {
    Q_OBJECT
private slots:
    /// Input test data
    /// @sa testTxtJson()
    void testReadTxt_data();

    /// Tests parsing of a TXT file
    void testReadTxt();
};

void TestAmdaResultParser::testReadTxt_data()
{
}

void TestAmdaResultParser::testReadTxt()
{
}

QTEST_MAIN(TestAmdaResultParser)
#include "TestAmdaResultParser.moc"
