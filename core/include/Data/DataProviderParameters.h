#ifndef SCIQLOP_DATAPROVIDERPARAMETERS_H
#define SCIQLOP_DATAPROVIDERPARAMETERS_H

#include "SqpRange.h"

/**
 * @brief The DataProviderParameters struct holds the information needed to retrieve data from a
 * data provider
 * @sa IDataProvider
 */
struct DataProviderParameters {
    /// Times for which retrieve data
    QVector<DateTimeRange> m_Times;
    /// Extra data that can be used by the provider to retrieve data
    QVariantHash m_Data;
};

#endif // SCIQLOP_DATAPROVIDERPARAMETERS_H
