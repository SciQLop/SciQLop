#ifndef SCIQLOP_COSINUSPROVIDER_H
#define SCIQLOP_COSINUSPROVIDER_H

#include "MockPluginGlobal.h"

#include <Data/IDataProvider.h>

#include <QLoggingCategory>
#include <QUuid>

#include <QHash>
Q_DECLARE_LOGGING_CATEGORY(LOG_CosinusProvider)

/**
 * @brief The CosinusProvider class is an example of how a data provider can generate data
 */
class SCIQLOP_MOCKPLUGIN_EXPORT CosinusProvider : public IDataProvider {
public:
    std::shared_ptr<IDataProvider> clone() const override;

    /// @sa IDataProvider::requestDataLoading(). The current impl isn't thread safe.
    void requestDataLoading(QUuid acqIdentifier, const DataProviderParameters &parameters) override;


    virtual IDataSeries* getData(const DataProviderParameters &parameters) override;

    /// @sa IDataProvider::requestDataAborting(). The current impl isn't thread safe.
    void requestDataAborting(QUuid acqIdentifier) override;


    /// Provide data
    std::shared_ptr<IDataSeries> provideDataSeries(const DateTimeRange &dataRangeRequested,
                                                   const QVariantHash &data);


private:
    std::shared_ptr<IDataSeries>
    retrieveData(QUuid acqIdentifier, const DateTimeRange &dataRangeRequested, const QVariantHash &data);

    IDataSeries* _generate(const DateTimeRange &range, const QVariantHash &metaData);

    QHash<QUuid, bool> m_VariableToEnableProvider;
};

#endif // SCIQLOP_COSINUSPROVIDER_H
