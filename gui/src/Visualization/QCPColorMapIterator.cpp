#include "Visualization/QCPColorMapIterator.h"

#include <Visualization/qcustomplot.h>

QCPColorMapIterator::QCPColorMapIterator(QCPColorMapData *data, bool begin)
        : m_Data{data}, m_KeyIndex{begin ? 0 : data->keySize()}, m_ValueIndex{0}
{
    updateValue();
}

QCPColorMapIterator &QCPColorMapIterator::operator++()
{
    // Increments indexes
    ++m_ValueIndex;
    if (m_ValueIndex == m_Data->valueSize()) {
        ++m_KeyIndex;
        m_ValueIndex = 0;
    }

    // Updates value
    updateValue();

    return *this;
}

QCPColorMapIterator QCPColorMapIterator::operator++(int)
{
    auto result = *this;
    this->operator++();
    return result;
}

QCPColorMapIterator::pointer QCPColorMapIterator::operator->() const
{
    return &m_Value;
}

QCPColorMapIterator::reference QCPColorMapIterator::operator*() const
{
    return m_Value;
}

bool QCPColorMapIterator::operator==(const QCPColorMapIterator &other)
{
    return std::tie(m_Data, m_KeyIndex, m_ValueIndex)
           == std::tie(other.m_Data, other.m_KeyIndex, other.m_ValueIndex);
}

bool QCPColorMapIterator::operator!=(const QCPColorMapIterator &other)
{
    return !(*this == other);
}

void QCPColorMapIterator::updateValue()
{
    m_Value = m_KeyIndex != m_Data->keySize() ? m_Data->cell(m_KeyIndex, m_ValueIndex)
                                              : std::numeric_limits<double>::quiet_NaN();
}
