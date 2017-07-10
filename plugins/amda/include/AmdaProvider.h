#ifndef SCIQLOP_AMDAPROVIDER_H
#define SCIQLOP_AMDAPROVIDER_H

#include "AmdaGlobal.h"

#include <Common/spimpl.h>

#include <Data/IDataProvider.h>

#include <QLoggingCategory>


Q_DECLARE_LOGGING_CATEGORY(LOG_AmdaProvider)

class QNetworkReply;

/**
 * @brief The AmdaProvider class is an example of how a data provider can generate data
 */
class SCIQLOP_AMDA_EXPORT AmdaProvider : public IDataProvider {
public:
    explicit AmdaProvider();

    void requestDataLoading(QUuid token, const QVector<SqpDateTime> &dateTimeList) override;

private:
    void retrieveData(QUuid token, const DataProviderParameters &parameters);

    class AmdaProviderPrivate;
    spimpl::unique_impl_ptr<AmdaProviderPrivate> impl;

    // private slots:
    //    void httpFinished(QNetworkReply *reply, QUuid dataId) noexcept;
    //    void httpDownloadFinished(QNetworkReply *reply, QUuid dataId) noexcept;
    //    void httpDownloadReadyRead(QNetworkReply *reply, QUuid dataId) noexcept;
};

#endif // SCIQLOP_AMDAPROVIDER_H
