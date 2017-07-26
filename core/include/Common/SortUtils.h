#ifndef SCIQLOP_SORTUTILS_H
#define SCIQLOP_SORTUTILS_H

#include <algorithm>
#include <numeric>
#include <vector>

/**
 * Utility class with methods for sorting data
 */
struct SortUtils {
    /**
     * Generates a vector representing the index of insertion of each data of a container if this
     * one had to be sorted according to a comparison function.
     *
     * For example:
     * If the container is a vector {1; 4; 2; 5; 3} and the comparison function is std::less, the
     * result would be : {0; 3; 1; 4; 2}
     *
     * @tparam Container the type of the container.
     * @tparam Compare the type of the comparison function
     * @param container the container from which to generate the result. The container must have a
     * at() method that returns a value associated to an index
     * @param compare the comparison function
     */
    template <typename Container, typename Compare>
    static std::vector<int> sortPermutation(const Container &container, const Compare &compare)
    {
        auto permutation = std::vector<int>{};
        permutation.resize(container.size());

        std::iota(permutation.begin(), permutation.end(), 0);
        std::sort(permutation.begin(), permutation.end(),
                  [&](int i, int j) { return compare(container.at(i), container.at(j)); });
        return permutation;
    }
};

#endif // SCIQLOP_SORTUTILS_H
