#ifndef SCIQLOP_AMDAPROVIDER_H
#define SCIQLOP_AMDAPROVIDER_H

#include "AmdaGlobal.h"

#include <Common/spimpl.h>

#include <Data/IDataProvider.h>

#include <QLoggingCategory>


Q_DECLARE_LOGGING_CATEGORY(LOG_AmdaProvider)

/**
 * @brief The AmdaProvider class is an example of how a data provider can generate data
 */
class SCIQLOP_AMDA_EXPORT AmdaProvider : public IDataProvider {
public:
    explicit AmdaProvider();

    void requestDataLoading(QUuid token, const QVector<SqpDateTime> &dateTimeList) override;

private:
    void retrieveData(QUuid token, const DataProviderParameters &parameters) const;

    class AmdaProviderPrivate;
    spimpl::unique_impl_ptr<AmdaProviderPrivate> impl;

private slots:
    void httpFinished() noexcept;
    void httpDownloadFinished() noexcept;
    void httpDownloadReadyRead() noexcept;
};

#endif // SCIQLOP_AMDAPROVIDER_H
