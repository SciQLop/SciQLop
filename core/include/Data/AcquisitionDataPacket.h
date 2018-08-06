#ifndef SCIQLOP_ACQUISITIONDATAPACKET_H
#define SCIQLOP_ACQUISITIONDATAPACKET_H

#include <QObject>

#include <Common/DateUtils.h>
#include <Common/MetaTypes.h>
#include <Data/IDataSeries.h>
#include <Data/SqpRange.h>

#include <memory>

/**
 * @brief The AcquisitionDataPacket struct holds the information of an acquisition request result
 * part.
 */
struct AcquisitionDataPacket {
    std::shared_ptr<IDataSeries> m_DateSeries;
    DateTimeRange m_Range;
};

SCIQLOP_REGISTER_META_TYPE(ACQUISITIONDATAPACKET_REGISTRY, AcquisitionDataPacket)
SCIQLOP_REGISTER_META_TYPE(ACQUISITIONDATAPACKETVECTOR_REGISTRY, QVector<AcquisitionDataPacket>)

#endif // SCIQLOP_ACQUISITIONREQUEST_H
