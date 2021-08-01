#include <Data/DataProviderParameters.h>
#include <Data/IDataProvider.h>
#include <Data/ScalarTimeSerie.h>

class DataSource : public IDataProvider {
public:
  DataSource();
  virtual ~DataSource() = default;
  TimeSeries::ITimeSerie *
  getData(const DataProviderParameters &parameters) final;
};
