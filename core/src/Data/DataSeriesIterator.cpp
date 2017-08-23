#include "Data/DataSeriesIterator.h"

DataSeriesIteratorValue::DataSeriesIteratorValue(
    std::unique_ptr<DataSeriesIteratorValue::Impl> impl)
        : m_Impl{std::move(impl)}
{
}

DataSeriesIteratorValue::DataSeriesIteratorValue(const DataSeriesIteratorValue &other)
        : m_Impl{other.m_Impl->clone()}
{
}

DataSeriesIteratorValue &DataSeriesIteratorValue::operator=(DataSeriesIteratorValue other)
{
    std::swap(m_Impl, other.m_Impl);
    return *this;
}

bool DataSeriesIteratorValue::equals(const DataSeriesIteratorValue &other) const
{
    return m_Impl->equals(*other.m_Impl);
}

void DataSeriesIteratorValue::next()
{
    m_Impl->next();
}

void DataSeriesIteratorValue::prev()
{
    m_Impl->prev();
}

double DataSeriesIteratorValue::x() const
{
    return m_Impl->x();
}

double DataSeriesIteratorValue::value() const
{
    return m_Impl->value();
}

double DataSeriesIteratorValue::value(int componentIndex) const
{
    return m_Impl->value(componentIndex);
}

double DataSeriesIteratorValue::minValue() const
{
    return m_Impl->minValue();
}

double DataSeriesIteratorValue::maxValue() const
{
    return m_Impl->maxValue();
}

DataSeriesIterator::DataSeriesIterator(DataSeriesIteratorValue value)
        : m_CurrentValue{std::move(value)}
{
}

DataSeriesIterator &DataSeriesIterator::operator++()
{
    m_CurrentValue.next();
    return *this;
}

DataSeriesIterator &DataSeriesIterator::operator--()
{
    m_CurrentValue.prev();
    return *this;
}

bool DataSeriesIterator::operator==(const DataSeriesIterator &other) const
{
    return m_CurrentValue.equals(other.m_CurrentValue);
}

bool DataSeriesIterator::operator!=(const DataSeriesIterator &other) const
{
    return !(*this == other);
}
