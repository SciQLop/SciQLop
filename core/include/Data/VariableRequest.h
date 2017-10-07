#ifndef SCIQLOP_VARIABLEREQUEST_H
#define SCIQLOP_VARIABLEREQUEST_H

#include <QObject>

#include <QUuid>

#include <Common/MetaTypes.h>
#include <Data/IDataSeries.h>
#include <Data/SqpRange.h>

#include <memory>

/**
 * @brief The VariableRequest struct holds the information of an acquisition request
 */
struct VariableRequest {
    QUuid m_VariableGroupId;
    SqpRange m_RangeRequested;
    SqpRange m_CacheRangeRequested;
    std::shared_ptr<IDataSeries> m_DataSeries;
};

SCIQLOP_REGISTER_META_TYPE(VARIABLEREQUEST_REGISTRY, VariableRequest)

#endif // SCIQLOP_VARIABLEREQUEST_H
