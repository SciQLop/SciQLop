#ifndef SCIQLOP_DATAPROVIDERPARAMETERS_H
#define SCIQLOP_DATAPROVIDERPARAMETERS_H

#include "SqpDateTime.h"

/**
 * @brief The DataProviderParameters struct holds the information needed to retrieve data from a
 * data provider
 * @sa IDataProvider
 */
struct DataProviderParameters {
    SqpDateTime m_Time;
};

#endif // SCIQLOP_DATAPROVIDERPARAMETERS_H
