#ifndef SCIQLOP_DATASERIESMERGEHELPER_H
#define SCIQLOP_DATASERIESMERGEHELPER_H

template <int Dim>
class DataSeries;

namespace detail {

/**
 * Scope that can be used for a merge operation
 * @tparam FEnd the type of function that will be executed at the end of the scope
 */
template <typename FEnd>
struct MergeScope {
    explicit MergeScope(FEnd end) : m_End{end} {}
    virtual ~MergeScope() noexcept { m_End(); }
    FEnd m_End;
};

/**
 * Creates a scope for merge operation
 * @tparam end the function executed at the end of the scope
 */
template <typename FEnd>
MergeScope<FEnd> scope(FEnd end)
{
    return MergeScope<FEnd>{end};
}

/**
 * Enum used to position a data series relative to another during a merge operation
 */
enum class MergePosition { LOWER_THAN, GREATER_THAN, EQUAL, OVERLAP };

/**
 * Computes the position of the first data series relative to the second data series
 * @param lhs the first data series
 * @param rhs the second data series
 * @return the merge position computed
 * @remarks the data series must not be empty
 */
template <int Dim>
MergePosition mergePosition(DataSeries<Dim> &lhs, DataSeries<Dim> &rhs)
{
    Q_ASSERT(!lhs.isEmpty() && !rhs.isEmpty());

    // Case lhs < rhs
    auto lhsLast = --lhs.cend();
    auto rhsFirst = rhs.cbegin();
    if (lhsLast->x() < rhsFirst->x()) {
        return MergePosition::LOWER_THAN;
    }

    // Case lhs > rhs
    auto lhsFirst = lhs.cbegin();
    auto rhsLast = --rhs.cend();
    if (lhsFirst->x() > rhsLast->x()) {
        return MergePosition::GREATER_THAN;
    }

    // Other cases
    auto equal = std::equal(lhs.cbegin(), lhs.cend(), rhs.cbegin(), rhs.cend(),
                            [](const auto &it1, const auto &it2) {
                                return it1.x() == it2.x() && it1.values() == it2.values();
                            });
    return equal ? MergePosition::EQUAL : MergePosition::OVERLAP;
}

} // namespace detail


/// Helper used to merge two DataSeries
/// @sa DataSeries
struct DataSeriesMergeHelper {
    /// Merges the source data series into the dest data series. Data of the source data series are
    /// consumed
    template <int Dim>
    static void merge(DataSeries<Dim> &source, DataSeries<Dim> &dest)
    {
        // Creates a scope to clear source data series at the end of the merge
        auto _ = detail::scope([&source]() { source.clear(); });

        // Case : source data series is empty -> no merge is made
        if (source.isEmpty()) {
            return;
        }

        // Case : dest data series is empty -> we simply swap the data
        if (dest.isEmpty()) {
            std::swap(dest.m_XAxisData, source.m_XAxisData);
            std::swap(dest.m_ValuesData, source.m_ValuesData);
            return;
        }

        // Gets the position of the source in relation to the destination
        auto sourcePosition = detail::mergePosition(source, dest);

        switch (sourcePosition) {
            case detail::MergePosition::LOWER_THAN:
            case detail::MergePosition::GREATER_THAN: {
                auto prepend = sourcePosition == detail::MergePosition::LOWER_THAN;
                dest.m_XAxisData->add(*source.m_XAxisData, prepend);
                dest.m_ValuesData->add(*source.m_ValuesData, prepend);
                break;
            }
            case detail::MergePosition::EQUAL:
                // the data series equal each other : no merge made
                break;
            case detail::MergePosition::OVERLAP: {
                // the two data series overlap : merge is made
                auto temp = dest.clone();
                if (auto tempSeries = dynamic_cast<DataSeries<Dim> *>(temp.get())) {
                    // Makes the merge :
                    // - Data are sorted by x-axis values
                    // - If two entries are in the source range and the other range, only one entry
                    // is retained as result
                    // - The results are stored directly in the data series
                    dest.clear();
                    std::set_union(
                        tempSeries->cbegin(), tempSeries->cend(), source.cbegin(), source.cend(),
                        std::back_inserter(dest),
                        [](const auto &it1, const auto &it2) { return it1.x() < it2.x(); });
                }
                break;
            }
            default:
                Q_ASSERT(false);
        }
    }
};

#endif // SCIQLOP_DATASERIESMERGEHELPER_H
