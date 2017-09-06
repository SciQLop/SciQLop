#include "Data/ArrayDataIterator.h"

ArrayDataIteratorValue::ArrayDataIteratorValue(std::unique_ptr<ArrayDataIteratorValue::Impl> impl)
        : m_Impl{std::move(impl)}
{
}

ArrayDataIteratorValue::ArrayDataIteratorValue(const ArrayDataIteratorValue &other)
        : m_Impl{other.m_Impl->clone()}
{
}

ArrayDataIteratorValue &ArrayDataIteratorValue::operator=(ArrayDataIteratorValue other)
{
    m_Impl->swap(*other.m_Impl);
    return *this;
}

int ArrayDataIteratorValue::distance(const ArrayDataIteratorValue &other) const
{
    return m_Impl->distance(*other.m_Impl);
}

bool ArrayDataIteratorValue::equals(const ArrayDataIteratorValue &other) const
{
    return m_Impl->equals(*other.m_Impl);
}

bool ArrayDataIteratorValue::lowerThan(const ArrayDataIteratorValue &other) const
{
    return m_Impl->lowerThan(*other.m_Impl);
}

ArrayDataIteratorValue ArrayDataIteratorValue::advance(int offset) const
{
    return ArrayDataIteratorValue{m_Impl->advance(offset)};
}

void ArrayDataIteratorValue::next(int offset)
{
    m_Impl->next(offset);
}

void ArrayDataIteratorValue::prev()
{
    m_Impl->prev();
}

double ArrayDataIteratorValue::at(int componentIndex) const
{
    return m_Impl->at(componentIndex);
}

double ArrayDataIteratorValue::first() const
{
    return m_Impl->first();
}

double ArrayDataIteratorValue::min() const
{
    return m_Impl->min();
}

double ArrayDataIteratorValue::max() const
{
    return m_Impl->max();
}

QVector<double> ArrayDataIteratorValue::values() const
{
    return m_Impl->values();
}

ArrayDataIteratorValue::Impl *ArrayDataIteratorValue::impl()
{
    return m_Impl.get();
}
