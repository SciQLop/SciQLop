#include <Data/OptionalAxis.h>

#include "Data/ArrayData.h"

OptionalAxis::OptionalAxis() : m_Defined{false}, m_Data{nullptr}, m_Unit{}
{
}

OptionalAxis::OptionalAxis(std::shared_ptr<ArrayData<1> > data, Unit unit)
        : m_Defined{true}, m_Data{data}, m_Unit{std::move(unit)}
{
    if (m_Data == nullptr) {
        throw std::invalid_argument{"Data can't be null for a defined axis"};
    }
}

OptionalAxis::OptionalAxis(const OptionalAxis &other)
        : m_Defined{other.m_Defined},
          m_Data{other.m_Data ? std::make_shared<ArrayData<1> >(*other.m_Data) : nullptr},
          m_Unit{other.m_Unit}
{
}

OptionalAxis &OptionalAxis::operator=(OptionalAxis other)
{
    std::swap(m_Defined, other.m_Defined);
    std::swap(m_Data, other.m_Data);
    std::swap(m_Unit, other.m_Unit);

    return *this;
}

bool OptionalAxis::isDefined() const
{
    return m_Defined;
}

double OptionalAxis::at(int index) const
{
    if (m_Defined) {
        return (index >= 0 && index < m_Data->size()) ? m_Data->at(index)
                                                      : std::numeric_limits<double>::quiet_NaN();
    }
    else {
        return std::numeric_limits<double>::quiet_NaN();
    }
}

std::pair<double, double> OptionalAxis::bounds() const
{
    if (!m_Defined || m_Data->size() == 0) {
        return std::make_pair(std::numeric_limits<double>::quiet_NaN(),
                              std::numeric_limits<double>::quiet_NaN());
    }
    else {

        auto minIt = std::min_element(
            m_Data->cbegin(), m_Data->cend(), [](const auto &it1, const auto &it2) {
                return SortUtils::minCompareWithNaN(it1.first(), it2.first());
            });

        // Gets the iterator on the max of all values data
        auto maxIt = std::max_element(
            m_Data->cbegin(), m_Data->cend(), [](const auto &it1, const auto &it2) {
                return SortUtils::maxCompareWithNaN(it1.first(), it2.first());
            });

        auto pair = std::make_pair(minIt->first(), maxIt->first());

        return std::make_pair(minIt->first(), maxIt->first());
    }
}

int OptionalAxis::size() const
{
    return m_Defined ? m_Data->size() : 0;
}

Unit OptionalAxis::unit() const
{
    return m_Defined ? m_Unit : Unit{};
}

bool OptionalAxis::operator==(const OptionalAxis &other)
{
    // Axis not defined
    if (!m_Defined) {
        return !other.m_Defined;
    }

    // Axis defined
    return m_Unit == other.m_Unit
           && std::equal(
                  m_Data->cbegin(), m_Data->cend(), other.m_Data->cbegin(), other.m_Data->cend(),
                  [](const auto &it1, const auto &it2) { return it1.values() == it2.values(); });
}

bool OptionalAxis::operator!=(const OptionalAxis &other)
{
    return !(*this == other);
}
