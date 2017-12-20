#include "FuzzingUtils.h"

RandomGenerator &RandomGenerator::instance()
{
    static auto instance = RandomGenerator();
    return instance;
}

double RandomGenerator::generateDouble(double min, double max)
{
    std::uniform_real_distribution<double> dist{min, max};
    return dist(m_Mt);
}

int RandomGenerator::generateInt(int min, int max)
{
    std::uniform_int_distribution<int> dist{min, max};
    return dist(m_Mt);
}

RandomGenerator::RandomGenerator()
{
    std::random_device rd{};
    m_Mt = std::mt19937{rd()};
}
