#include "DemoPlugin.hpp"
#include <iostream>
#include <DataSource/datasources.h>
#include <SqpApplication.h>

#include "DataSource.hpp"

void DemoPlugin::initialize()
{
    std::cout << "Loading DemoPlugin \\o/" << std::endl;
    auto& dataSources = sqpApp->dataSources();
    dataSources.addProvider<DataSource>();
}
