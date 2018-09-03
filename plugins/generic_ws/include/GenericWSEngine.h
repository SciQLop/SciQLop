#ifndef GENERICWSENGINE_H
#define GENERICWSENGINE_H
#include <Data/IDataProvider.h>
#include <Data/DataProviderParameters.h>

class GenericWSEngine: public IDataProvider
{
public:
    virtual std::shared_ptr<IDataProvider> clone() const override
    {
        return std::make_shared<GenericWSEngine>();
    }

    virtual IDataSeries* getData(const DataProviderParameters &parameters) override
    {
        auto range = parameters.m_Range;
        auto metadata = parameters.m_Data;
        auto WS = metadata["WS"].toString();
        auto parameter = metadata["WS"].toString();
        return nullptr;
    }


};

#endif
