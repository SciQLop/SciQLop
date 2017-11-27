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

} // namespace

AmdaServer &AmdaServer::instance()
{
    /// @todo ALX
}
