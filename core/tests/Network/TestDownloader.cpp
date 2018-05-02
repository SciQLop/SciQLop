#include <Network/Downloader.h>
#include <QtTest>
#include <QObject>


class TestDownloader : public QObject

{
    Q_OBJECT
public:
    explicit TestDownloader(QObject *parent = nullptr) : QObject(parent){}
signals:

private slots:
    void initTestCase(){}
    void cleanupTestCase(){}

    void simpleGet()
    {
        auto resp = Downloader::get("https://httpbin.org/user-agent");
        QCOMPARE(resp.status_code(), 200);
        QCOMPARE(resp.data(), QString("{\n  \"user-agent\": \"SciQLop 1.0\"\n}\n"));
    }

    void simpleAsyncGet()
    {
        bool done = false;
        int status = -1;
        QByteArray data;
        auto callback = [&done, &status, &data](QUuid uuid,Response resp)
            {
                status = resp.status_code();
                done = true;
                data = resp.data();
            };
        auto uuid = Downloader::getAsync("http://ovh.net/files/1Mio.dat", callback);
        QCOMPARE(Downloader::downloadFinished(uuid), false);
        while (!done)
        {
            QCoreApplication::processEvents();
        }
        QCOMPARE(Downloader::downloadFinished(uuid), true);
        QCOMPARE(status, 200);
        QCOMPARE(data[0],'\xBA');
        QCOMPARE(data[data.length()-1],'\x20');
    }

    void wrongUrl()
    {
        auto resp = Downloader::get("https://lpp.polytechniqe2.fr");
        QCOMPARE(resp.status_code(), 0);
        resp = Downloader::get("https://hephaistos.lpp.polytechnique.fr/will_never_exist");
        QCOMPARE(resp.status_code(), 404);

    }

    void authGet_data()
    {
        QTest::addColumn<QString>("url");
        QTest::addColumn<int>("code");

        QTest::newRow("basic-auth")  << "https://httpbin.org/basic-auth/user/passwd" << 200;
        QTest::newRow("digest-auth") << "https://httpbin.org/digest-auth/auth/user/passwd" << 200;
        QTest::newRow("hidden-basic-auth") << "https://httpbin.org/hidden-basic-auth/user/passwd" << 404;
    }

    void authGet()
    {
        QFETCH(QString, url);
        QFETCH(int, code);
        auto resp = Downloader::get(url, "user", "passwd");
        QCOMPARE(resp.status_code(), code);
    }

private:

};


QTEST_MAIN(TestDownloader)

#include "TestDownloader.moc"
