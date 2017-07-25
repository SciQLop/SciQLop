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
    /// @sa IDataProvider::requestDataLoading(). The current impl isn't thread safe.
    void requestDataLoading(QUuid token, const DataProviderParameters &parameters) override;


    /// @sa IDataProvider::requestDataAborting(). The current impl isn't thread safe.
    void requestDataAborting(QUuid identifier) override;


private:
    std::shared_ptr<IDataSeries> retrieveData(QUuid token, const SqpDateTime &dateTime);

    QHash<QUuid, bool> m_VariableToEnableProvider;
};

#endif // SCIQLOP_COSINUSPROVIDER_H
