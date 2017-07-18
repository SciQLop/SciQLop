#ifndef SCIQLOP_IDATAPROVIDER_H
#define SCIQLOP_IDATAPROVIDER_H

#include <memory>

#include <QObject>
#include <QUuid>

#include <Common/MetaTypes.h>

#include <Data/SqpDateTime.h>

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
class IDataProvider : public QObject {

    Q_OBJECT
public:
    virtual ~IDataProvider() noexcept = default;

    /**
     * @brief requestDataLoading provide datas for the data identified by identifier and parameters
     */
    virtual void requestDataLoading(QUuid identifier, const DataProviderParameters &parameters) = 0;

    /**
     * @brief requestDataAborting stop data loading of the data identified by identifier
     */
    virtual void requestDataAborting(QUuid identifier) = 0;

signals:
    /**
     * @brief dataProvided send dataSeries under dateTime and that corresponds of the data
     * identified by identifier
     */
    void dataProvided(QUuid identifier, std::shared_ptr<IDataSeries> dateSerie,
                      const SqpDateTime &dateTime);

    /**
        * @brief dataProvided send dataSeries under dateTime and that corresponds of the data
        * identified by identifier
        */
    void dataProvidedProgress(QUuid identifier, double progress);


    /**
     * @brief requestConstructed send a request for the data identified by identifier
     * @callback is the methode call by the reply of the request when it is finished.
     */
    void requestConstructed(const QNetworkRequest &request, QUuid identifier,
                            std::function<void(QNetworkReply *, QUuid)> callback);
};

// Required for using shared_ptr in signals/slots
SCIQLOP_REGISTER_META_TYPE(IDATAPROVIDER_PTR_REGISTRY, std::shared_ptr<IDataProvider>)
SCIQLOP_REGISTER_META_TYPE(IDATAPROVIDER_FUNCTION_REGISTRY,
                           std::function<void(QNetworkReply *, QUuid)>)

#endif // SCIQLOP_IDATAPROVIDER_H
