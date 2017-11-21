#ifndef SCIQLOP_SORTUTILS_H
#define SCIQLOP_SORTUTILS_H

#include <algorithm>
#include <cmath>
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

    /**
     * Sorts a container according to indices passed in parameter. The number of data in the
     * container must be a multiple of the number of indices used to sort the container.
     *
     * Example 1:
     * container: {1, 2, 3, 4, 5, 6}
     * sortPermutation: {1, 0}
     *
     * Values will be sorted three by three, and the result will be:
     * {4, 5, 6, 1, 2, 3}
     *
     * Example 2:
     * container: {1, 2, 3, 4, 5, 6}
     * sortPermutation: {2, 0, 1}
     *
     * Values will be sorted two by two, and the result will be:
     * {5, 6, 1, 2, 3, 4}
     *
     * @param container the container sorted
     * @param sortPermutation the indices used to sort the container
     * @return the container sorted
     * @warning no verification is made on validity of sortPermutation (i.e. the vector has unique
     * indices and its range is [0 ; vector.size()[ )
     */
    template <typename Container>
    static Container sort(const Container &container, int nbValues,
                          const std::vector<int> &sortPermutation)
    {
        auto containerSize = container.size();
        if (containerSize % nbValues != 0
            || ((containerSize / nbValues) != sortPermutation.size())) {
            return Container{};
        }

        // Inits result
        auto sortedData = Container{};
        sortedData.reserve(containerSize);

        for (auto i = 0u, componentIndex = 0u, permutationIndex = 0u; i < containerSize;
             ++i, componentIndex = i % nbValues, permutationIndex = i / nbValues) {
            auto insertIndex = sortPermutation.at(permutationIndex) * nbValues + componentIndex;
            sortedData.push_back(container.at(insertIndex));
        }

        return sortedData;
    }

    /**
     * Compares two values that can be NaN. This method is intended to be used as a compare function
     * for searching min value by excluding NaN values.
     *
     * Examples of use:
     * - f({1, 3, 2, 4, 5}) will return 1
     * - f({NaN, 3, 2, 4, 5}) will return 2 (NaN is excluded)
     * - f({NaN, NaN, 3, NaN, NaN}) will return 3 (NaN are excluded)
     * - f({NaN, NaN, NaN, NaN, NaN}) will return NaN (no existing value)
     *
     * @param v1 first value
     * @param v2 second value
     * @return true if v1 < v2, false otherwise
     * @sa std::min_element
     */
    template <typename T>
    static bool minCompareWithNaN(const T &v1, const T &v2)
    {
        // Table used with NaN values:
        // NaN < v2 -> false
        // v1 < NaN -> true
        // NaN < NaN -> false
        // v1 < v2 -> v1 < v2
        return std::isnan(v1) ? false : std::isnan(v2) || (v1 < v2);
    }

    /**
     * Compares two values that can be NaN. This method is intended to be used as a compare function
     * for searching max value by excluding NaN values.
     *
     * Examples of use:
     * - f({1, 3, 2, 4, 5}) will return 5
     * - f({1, 3, 2, 4, NaN}) will return 4 (NaN is excluded)
     * - f({NaN, NaN, 3, NaN, NaN}) will return 3 (NaN are excluded)
     * - f({NaN, NaN, NaN, NaN, NaN}) will return NaN (no existing value)
     *
     * @param v1 first value
     * @param v2 second value
     * @return true if v1 < v2, false otherwise
     * @sa std::max_element
     */
    template <typename T>
    static bool maxCompareWithNaN(const T &v1, const T &v2)
    {
        // Table used with NaN values:
        // NaN < v2 -> true
        // v1 < NaN -> false
        // NaN < NaN -> false
        // v1 < v2 -> v1 < v2
        return std::isnan(v1) ? true : !std::isnan(v2) && (v1 < v2);
    }
};

#endif // SCIQLOP_SORTUTILS_H
