#include "AmdaServer.h"

Q_LOGGING_CATEGORY(LOG_AmdaServer, "AmdaServer")

namespace {

/// Default AMDA server
struct AmdaDefaultServer : public AmdaServer {
public:
    QString name() const override { return QStringLiteral("AMDA (default)"); }
    QString url() const override { return QStringLiteral("amda.irap.omp.eu"); }
};

/// Alternative AMDA server (tests)
struct AmdaTestServer : public AmdaServer {
public:
    QString name() const override { return QStringLiteral("AMDA (test)"); }
    QString url() const override { return QStringLiteral("amdatest.irap.omp.eu"); }
};

/// @return an AMDA server instance created from the name of the server passed in parameter. If the
/// name does not match any known server, a default server instance is created
std::unique_ptr<AmdaServer> createInstance(const QString &server)
{
    if (server == QString{"amdatest"}) {
        return std::make_unique<AmdaTestServer>();
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
