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
    using iterator_category = std::forward_iterator_tag;
    using value_type = const T;
    using difference_type = std::ptrdiff_t;
    using pointer = value_type *;
    using reference = value_type &;

    explicit SqpIterator(T value) : m_CurrentValue{std::move(value)} {}

    virtual ~SqpIterator() noexcept = default;
    SqpIterator(const SqpIterator &) = default;
    SqpIterator(SqpIterator &&) = default;
    SqpIterator &operator=(const SqpIterator &) = default;
    SqpIterator &operator=(SqpIterator &&) = default;

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

    const T *operator->() const { return &m_CurrentValue; }
    const T &operator*() const { return m_CurrentValue; }
    T *operator->() { return &m_CurrentValue; }
    T &operator*() { return m_CurrentValue; }

    bool operator==(const SqpIterator &other) const
    {
        return m_CurrentValue.equals(other.m_CurrentValue);
    }
    bool operator!=(const SqpIterator &other) const { return !(*this == other); }

private:
    T m_CurrentValue;
};

#endif // SCIQLOP_SQPITERATOR_H
