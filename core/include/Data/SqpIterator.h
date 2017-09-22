#ifndef SCIQLOP_SQPITERATOR_H
#define SCIQLOP_SQPITERATOR_H

#include "CoreGlobal.h"

/**
 * @brief The SqpIterator class represents an iterator used in SciQlop. It defines all operators
 * needed for a standard forward iterator
 * @tparam T the type of object handled in iterator
 * @sa http://www.cplusplus.com/reference/iterator/
 */
template <typename T>
class SCIQLOP_CORE_EXPORT SqpIterator {
public:
    using iterator_category = std::random_access_iterator_tag;
    using value_type = const T;
    using difference_type = std::ptrdiff_t;
    using pointer = value_type *;
    using reference = value_type &;

    explicit SqpIterator(T value) : m_CurrentValue{std::move(value)} {}

    virtual ~SqpIterator() noexcept = default;
    SqpIterator(const SqpIterator &) = default;
    SqpIterator &operator=(SqpIterator other)
    {
        swap(m_CurrentValue, other.m_CurrentValue);
        return *this;
    }

    SqpIterator &operator++()
    {
        m_CurrentValue.next();
        return *this;
    }

    SqpIterator &operator--()
    {
        m_CurrentValue.prev();
        return *this;
    }

    SqpIterator operator++(int)const
    {
        auto result = *this;
        this->operator++();
        return result;
    }
    SqpIterator operator--(int)const
    {
        auto result = *this;
        this->operator--();
        return result;
    }

    SqpIterator &operator+=(int offset)
    {
        if (offset >= 0) {
            m_CurrentValue.next(offset);
        }
        else {
            while (offset++) {
                m_CurrentValue.prev();
            }
        }

        return *this;
    }
    SqpIterator &operator-=(int offset) { return *this += -offset; }

    SqpIterator operator+(int offset) const
    {
        auto result = *this;
        result += offset;
        return result;
    }
    SqpIterator operator-(int offset) const
    {
        auto result = *this;
        result -= offset;
        return result;
    }

    int operator-(const SqpIterator &other) const
    {
        return m_CurrentValue.distance(other.m_CurrentValue);
    }

    const T *operator->() const { return &m_CurrentValue; }
    const T &operator*() const { return m_CurrentValue; }
    T *operator->() { return &m_CurrentValue; }
    T &operator*() { return m_CurrentValue; }
    T &operator[](int offset) const { return m_CurrentValue.advance(offset); }

    bool operator==(const SqpIterator &other) const
    {
        return m_CurrentValue.equals(other.m_CurrentValue);
    }
    bool operator!=(const SqpIterator &other) const { return !(*this == other); }
    bool operator>(const SqpIterator &other) const { return other.m_CurrentValue.lowerThan(*this); }
    bool operator<(const SqpIterator &other) const
    {
        return m_CurrentValue.lowerThan(other.m_CurrentValue);
    }
    bool operator>=(const SqpIterator &other) const { return !(*this < other); }
    bool operator<=(const SqpIterator &other) const { return !(*this > other); }

private:
    T m_CurrentValue;
};

#endif // SCIQLOP_SQPITERATOR_H
