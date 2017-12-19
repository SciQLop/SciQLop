#ifndef SCIQLOP_FUZZINGUTILS_H
#define SCIQLOP_FUZZINGUTILS_H

#include <algorithm>
#include <random>

/**
 * Class that proposes random utility methods
 */
class RandomGenerator {
public:
    /// @return the unique instance of the random generator
    static RandomGenerator &instance();

    /// Generates a random double between [min, max]
    double generateDouble(double min, double max);
    /// Generates a random int between [min, max]
    int generateInt(int min, int max);

    /**
     * Returns a random element among the elements of a container. An item may be more likely to be
     * selected if it has an associated weight greater than other items
     * @param container the container from which to retrieve an element
     * @param weights the weight associated to each element of the container. The vector must have
     * the same size of the container for the weights to be effective
     * @param nbDraws the number of random draws to perform
     * @return the random element retrieved, an element built by default if the container is empty
     */
    template <typename T, typename ValueType = typename T::value_type>
    ValueType randomChoice(const T &container, const std::vector<double> &weights = {});

private:
    std::mt19937 m_Mt;

    explicit RandomGenerator();
};

template <typename T, typename ValueType>
ValueType RandomGenerator::randomChoice(const T &container, const std::vector<double> &weights)
{
    if (container.empty()) {
        return ValueType{};
    }

    // Generates weights for each element: if the weights passed in parameter are malformed (the
    // number of weights defined is inconsistent with the number of elements in the container, or
    // all weights are zero), default weights are used
    auto nbIndexes = container.size();
    std::vector<double> indexWeights(nbIndexes);
    if (weights.size() != nbIndexes || std::all_of(weights.cbegin(), weights.cend(),
                                                   [](const auto &val) { return val == 0.; })) {
        std::fill(indexWeights.begin(), indexWeights.end(), 1.);
    }
    else {
        std::copy(weights.begin(), weights.end(), indexWeights.begin());
    }

    // Performs a draw to determine the index to return
    std::discrete_distribution<> d{indexWeights.cbegin(), indexWeights.cend()};
    return container.at(d(m_Mt));
}

#endif // SCIQLOP_FUZZINGUTILS
