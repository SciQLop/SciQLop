#ifndef SCIQLOP_COSINUSPROVIDER_H
#define SCIQLOP_COSINUSPROVIDER_H

#include "MockPluginGlobal.h"

#include <Data/IDataProvider.h>

#include <QLoggingCategory>
#include <QUuid>

#include <QHash>

/**
 * @brief The CosinusProvider class is an example of how a data provider can generate data
 */
class SCIQLOP_MOCKPLUGIN_EXPORT CosinusProvider : public IDataProvider
{
public:
    std::shared_ptr<IDataProvider> clone() const override;

    virtual TimeSeries::ITimeSerie* getData(const DataProviderParameters& parameters) override;

private:
    std::shared_ptr<IDataSeries> retrieveData(
        QUuid acqIdentifier, const DateTimeRange& dataRangeRequested, const QVariantHash& data);

    TimeSeries::ITimeSerie* _generate(const DateTimeRange& range, const QVariantHash& metaData);

    QHash<QUuid, bool> m_VariableToEnableProvider;
};

#endif // SCIQLOP_COSINUSPROVIDER_H
