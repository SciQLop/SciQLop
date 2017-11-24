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
    m_Impl->swap(*other.m_Impl);
    return *this;
}

int DataSeriesIteratorValue::distance(const DataSeriesIteratorValue &other) const
{
    return m_Impl->distance(*other.m_Impl);
}

bool DataSeriesIteratorValue::equals(const DataSeriesIteratorValue &other) const
{
    return m_Impl->equals(*other.m_Impl);
}

bool DataSeriesIteratorValue::lowerThan(const DataSeriesIteratorValue &other) const
{
    return m_Impl->lowerThan(*other.m_Impl);
}

DataSeriesIteratorValue DataSeriesIteratorValue::advance(int offset) const
{
    return DataSeriesIteratorValue{m_Impl->advance(offset)};
}

void DataSeriesIteratorValue::next(int offset)
{
    m_Impl->next(offset);
}

void DataSeriesIteratorValue::prev()
{
    m_Impl->prev();
}

double DataSeriesIteratorValue::x() const
{
    return m_Impl->x();
}

std::vector<double> DataSeriesIteratorValue::y() const
{
    return m_Impl->y();
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

QVector<double> DataSeriesIteratorValue::values() const
{
    return m_Impl->values();
}

DataSeriesIteratorValue::Impl *DataSeriesIteratorValue::impl()
{
    return m_Impl.get();
}
