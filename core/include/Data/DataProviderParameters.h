#ifndef SCIQLOP_DATAPROVIDERPARAMETERS_H
#define SCIQLOP_DATAPROVIDERPARAMETERS_H

/**
 * @brief The DataProviderParameters struct holds the information needed to retrieve data from a
 * data provider
 * @sa IDataProvider
 */
struct DataProviderParameters {
    /// Start time
    double m_TStart;
    /// End time
    double m_TEnd;
};

#endif // SCIQLOP_DATAPROVIDERPARAMETERS_H
