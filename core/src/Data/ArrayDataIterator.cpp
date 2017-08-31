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

bool ArrayDataIteratorValue::equals(const ArrayDataIteratorValue &other) const
{
    return m_Impl->equals(*other.m_Impl);
}

void ArrayDataIteratorValue::next()
{
    m_Impl->next();
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
