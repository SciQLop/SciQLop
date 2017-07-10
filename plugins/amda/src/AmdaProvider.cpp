#include "AmdaProvider.h"

Q_LOGGING_CATEGORY(LOG_AmdaProvider, "AmdaProvider")

struct AmdaProvider::AmdaProviderPrivate {
};

AmdaProvider::AmdaProvider() : impl{spimpl::make_unique_impl<AmdaProviderPrivate>()}
{
}

void AmdaProvider::requestDataLoading(QUuid token, const QVector<SqpDateTime> &dateTimeList)
{
    // NOTE: Try to use multithread if possible
    for (const auto &dateTime : dateTimeList) {
        retrieveData(token, DataProviderParameters{dateTime});
    }
}

void AmdaProvider::retrieveData(QUuid token, const DataProviderParameters &parameters) const
{
    /// @todo ALX
}
