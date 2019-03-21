#ifndef SCIQLOP_AMDAPROVIDER_H
#define SCIQLOP_AMDAPROVIDER_H

#include "AmdaGlobal.h"

#include <Data/IDataProvider.h>

#include <QLoggingCategory>

#include <map>

Q_DECLARE_LOGGING_CATEGORY(LOG_AmdaProvider)

class QNetworkReply;
class QNetworkRequest;

/**
 * @brief The AmdaProvider class is an example of how a data provider can generate data
 */
class SCIQLOP_AMDA_EXPORT AmdaProvider : public IDataProvider
{
    Q_OBJECT
public:
    explicit AmdaProvider();
    std::shared_ptr<IDataProvider> clone() const override;

    virtual TimeSeries::ITimeSerie* getData(const DataProviderParameters& parameters) override;
};

#endif // SCIQLOP_AMDAPROVIDER_H
