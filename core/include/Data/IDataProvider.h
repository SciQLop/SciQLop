#ifndef SCIQLOP_IDATAPROVIDER_H
#define SCIQLOP_IDATAPROVIDER_H

#include "CoreGlobal.h"

#include <memory>

#include <QObject>
#include <QUuid>

#include <Common/MetaTypes.h>

#include <Data/SqpRange.h>

#include <functional>

class DataProviderParameters;
class IDataSeries;
class QNetworkReply;
class QNetworkRequest;

/**
 * @brief The IDataProvider interface aims to declare a data provider.
 *
 * A data provider is an entity that generates data and returns it according to various parameters
 * (time interval, product to retrieve the data, etc.)
 *
 * @sa IDataSeries
 */
class SCIQLOP_CORE_EXPORT IDataProvider : public QObject {

    Q_OBJECT
public:
    virtual ~IDataProvider() noexcept = default;
    virtual std::shared_ptr<IDataProvider> clone() const = 0;

    /**
     * @brief requestDataLoading provide datas for the data identified by acqIdentifier and
     * parameters
     */
    virtual void requestDataLoading(QUuid acqIdentifier, const DataProviderParameters &parameters)
        = 0;

    /**
     * @brief requestDataAborting stop data loading of the data identified by acqIdentifier
     */
    virtual void requestDataAborting(QUuid acqIdentifier) = 0;

signals:
    /**
     * @brief dataProvided send dataSeries under dateTime and that corresponds of the data
     * identified by acqIdentifier
     */
    void dataProvided(QUuid acqIdentifier, std::shared_ptr<IDataSeries> dateSeriesAcquired,
                      const DateTimeRange &dataRangeAcquired);

    /**
     * @brief dataProvidedProgress notify the progression of the data identifier by acqIdentifier
     */
    void dataProvidedProgress(QUuid acqIdentifier, double progress);

    /**
     * @brief dataProvidedFailed notify that data acquisition has failed
     */
    void dataProvidedFailed(QUuid acqIdentifier);


    /**
     * @brief requestConstructed send a request for the data identified by acqIdentifier
     * @callback is the methode call by the reply of the request when it is finished.
     */
    void requestConstructed(std::shared_ptr<QNetworkRequest> request, QUuid acqIdentifier,
                            std::function<void(QNetworkReply *, QUuid)> callback);
};

// Required for using shared_ptr in signals/slots
SCIQLOP_REGISTER_META_TYPE(IDATAPROVIDER_PTR_REGISTRY, std::shared_ptr<IDataProvider>)
SCIQLOP_REGISTER_META_TYPE(IDATAPROVIDER_FUNCTION_REGISTRY,
                           std::function<void(QNetworkReply *, QUuid)>)

#endif // SCIQLOP_IDATAPROVIDER_H
