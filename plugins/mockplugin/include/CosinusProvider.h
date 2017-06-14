#ifndef SCIQLOP_COSINUSPROVIDER_H
#define SCIQLOP_COSINUSPROVIDER_H

#include <Data/IDataProvider.h>

/**
 * @brief The CosinusProvider class is an example of how a data provider can generate data
 */
class CosinusProvider : public IDataProvider {
public:
    /// @sa IDataProvider::retrieveData()
    std::unique_ptr<IDataSeries>
    retrieveData(const DataProviderParameters &parameters) const override;
};

#endif // SCIQLOP_COSINUSPROVIDER_H
