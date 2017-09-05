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

        auto destMin = dest.cbegin()->x();
        auto destMax = (--dest.cend())->x();

        auto sourceBegin = source.cbegin();
        auto sourceEnd = source.cend();
        auto sourceMin = sourceBegin->x();
        auto sourceMax = (--source.cend())->x();

        // Case : source bounds are inside dest bounds -> no merge is made
        if (sourceMin >= destMin && sourceMax <= destMax) {
            return;
        }

        // Default case :
        // - prepend to dest the values of source that are lower than min value of dest
        // - append to dest the values of source that are greater than max value of dest
        auto lowerIt
            = std::lower_bound(sourceBegin, sourceEnd, destMin,
                               [](const auto &it, const auto &val) { return it.x() < val; });
        auto upperIt
            = std::upper_bound(lowerIt, sourceEnd, destMax,
                               [](const auto &val, const auto &it) { return val < it.x(); });
        dest.insert(sourceBegin, lowerIt, true);
        dest.insert(upperIt, sourceEnd);
    }
};

#endif // SCIQLOP_DATASERIESMERGEHELPER_H
