#ifndef SCIQLOP_ACQUISITIONREQUEST_H
#define SCIQLOP_ACQUISITIONREQUEST_H

#include <QObject>

#include <QUuid>

#include <Common/DateUtils.h>
#include <Common/MetaTypes.h>
#include <Data/DataProviderParameters.h>
#include <Data/IDataProvider.h>
#include <Data/SqpRange.h>

#include <memory>

/**
 * @brief The AcquisitionRequest struct holds the information of an acquisition request
 */
struct AcquisitionRequest {
    AcquisitionRequest()
    {

        m_AcqIdentifier = QUuid::createUuid();
        m_Size = 0;
    }

    QUuid m_AcqIdentifier;
    QUuid m_vIdentifier;
    DataProviderParameters m_DataProviderParameters;
    SqpRange m_RangeRequested;
    SqpRange m_CacheRangeRequested;
    int m_Size;
    std::shared_ptr<IDataProvider> m_Provider;
};

SCIQLOP_REGISTER_META_TYPE(ACQUISITIONREQUEST_REGISTRY, AcquisitionRequest)

#endif // SCIQLOP_ACQUISITIONREQUEST_H
