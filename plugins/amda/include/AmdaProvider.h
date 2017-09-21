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
class SCIQLOP_AMDA_EXPORT AmdaProvider : public IDataProvider {
    Q_OBJECT
public:
    explicit AmdaProvider();
    std::shared_ptr<IDataProvider> clone() const override;

    void requestDataLoading(QUuid acqIdentifier, const DataProviderParameters &parameters) override;

    void requestDataAborting(QUuid acqIdentifier) override;

private slots:
    void onReplyDownloadProgress(QUuid acqIdentifier,
                                 std::shared_ptr<QNetworkRequest> networkRequest, double progress);

private:
    void retrieveData(QUuid token, const SqpRange &dateTime, const QVariantHash &data);

    void updateRequestProgress(QUuid acqIdentifier, std::shared_ptr<QNetworkRequest> request,
                               double progress);

    std::map<QUuid, std::map<std::shared_ptr<QNetworkRequest>, double> >
        m_AcqIdToRequestProgressMap;
};

#endif // SCIQLOP_AMDAPROVIDER_H
