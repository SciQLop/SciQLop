#include "AmdaServer.h"

#include "AmdaDefs.h"

Q_LOGGING_CATEGORY(LOG_AmdaServer, "AmdaServer")

namespace {

/// URL of the default AMDA server
const auto AMDA_DEFAULT_SERVER_URL = QStringLiteral("amda.irap.omp.eu");

/// URL of the AMDA test server
const auto AMDA_TEST_SERVER_URL = QStringLiteral("amdadev.irap.omp.eu/");

/// Port used for local server
const auto AMDA_LOCAL_SERVER_PORT = 6543;

/// URL of the local server
const auto AMDA_LOCAL_SERVER_URL
    = QString{"localhost:%1"}.arg(QString::number(AMDA_LOCAL_SERVER_PORT));

/// Default AMDA server
struct AmdaDefaultServer : public AmdaServer {
public:
    QString name() const override { return QStringLiteral("AMDA (default)"); }
    QString url(const QVariantHash &properties) const override
    {
        Q_UNUSED(properties);
        return AMDA_DEFAULT_SERVER_URL;
    }
};

/// Alternative AMDA server (tests)
struct AmdaTestServer : public AmdaServer {
public:
    QString name() const override { return QStringLiteral("AMDA (test)"); }
    QString url(const QVariantHash &properties) const override
    {
        Q_UNUSED(properties);
        return AMDA_TEST_SERVER_URL;
    }
};

/// Hybrid AMDA server: use both of default and test server.
/// The server used is relative to each product for which to retrieve url, according to its "server"
/// property
struct AmdaHybridServer : public AmdaServer {
public:
    QString name() const override { return QStringLiteral("AMDA (hybrid)"); }
    QString url(const QVariantHash &properties) const override
    {
        // Reads "server" property to determine which server url to use
        auto server = properties.value(AMDA_SERVER_KEY).toString();
        return server == QString{"amdatest"} ? AMDA_TEST_SERVER_URL : AMDA_DEFAULT_SERVER_URL;
    }
};

/// Local AMDA server: use local python server to simulate AMDA requests
struct AmdaLocalServer : public AmdaServer {
public:
    QString name() const override { return AMDA_LOCAL_SERVER_URL; }
    QString url(const QVariantHash &properties) const override
    {
        Q_UNUSED(properties);
        return AMDA_LOCAL_SERVER_URL;
    }
};

/// @return an AMDA server instance created from the name of the server passed in parameter. If the
/// name does not match any known server, a default server instance is created
std::unique_ptr<AmdaServer> createInstance(const QString &server)
{
    if (server == QString{"amdatest"}) {
        return std::make_unique<AmdaTestServer>();
    }
    else if (server == QString{"hybrid"}) {
        return std::make_unique<AmdaHybridServer>();
    }
    else if (server == QString{"localhost"}) {
        return std::make_unique<AmdaLocalServer>();
    }
    else {
        if (server != QString{"default"}) {
            qCWarning(LOG_AmdaServer())
                << QObject::tr("Unknown server '%1': default AMDA server will be used").arg(server);
        }

        return std::make_unique<AmdaDefaultServer>();
    }
}

} // namespace

AmdaServer &AmdaServer::instance()
{
    // Creates instance depending on the SCIQLOP_AMDA_SERVER value at compile time
    static auto instance = createInstance(SCIQLOP_AMDA_SERVER);
    return *instance;
}
