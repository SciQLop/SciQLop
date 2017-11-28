#ifndef SCIQLOP_QCPCOLORMAPITERATOR_H
#define SCIQLOP_QCPCOLORMAPITERATOR_H

#include <iterator>

class QCPColorMapData;

/**
 * Forward iterator for @sa QCPColorMap
 */
class QCPColorMapIterator {
public:
    using iterator_category = std::forward_iterator_tag;
    using value_type = double;
    using difference_type = std::ptrdiff_t;
    using pointer = const value_type *;
    using reference = value_type;

    explicit QCPColorMapIterator(QCPColorMapData *data, bool begin);
    virtual ~QCPColorMapIterator() noexcept = default;

    QCPColorMapIterator &operator++();
    QCPColorMapIterator operator++(int);

    pointer operator->() const;
    reference operator*() const;

    bool operator==(const QCPColorMapIterator &other);
    bool operator!=(const QCPColorMapIterator &other);

private:
    void updateValue();

    QCPColorMapData *m_Data; ///< Data iterated
    int m_KeyIndex;          ///< Current iteration key index
    int m_ValueIndex;        ///< Current iteration value index
    double m_Value;          ///< Current iteration value
};

#endif // SCIQLOP_QCPCOLORMAPITERATOR_H
