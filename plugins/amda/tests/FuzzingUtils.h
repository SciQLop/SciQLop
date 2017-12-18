#ifndef SCIQLOP_FUZZINGUTILS_H
#define SCIQLOP_FUZZINGUTILS_H

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

    /// Returns a random element among the elements of a container. If the container is empty,
    /// returns an element built by default
    template <typename T, typename ValueType = typename T::value_type>
    ValueType randomChoice(const T &container);

private:
    std::mt19937 m_Mt;

    explicit RandomGenerator();
};

template <typename T, typename ValueType>
ValueType RandomGenerator::randomChoice(const T &container)
{
    if (container.empty()) {
        return ValueType{};
    }

    auto randomIndex = generateInt(0, container.size() - 1);
    return container.at(randomIndex);
}

#endif // SCIQLOP_FUZZINGUTILS
