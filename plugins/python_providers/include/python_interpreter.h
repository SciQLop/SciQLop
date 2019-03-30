#include <Data/DateTimeRange.h>
#include <TimeSeries.h>
#include <functional>
#include <iostream>
#include <memory>


class PythonInterpreter
{
public:
    using provider_funct_t = std::function<std::shared_ptr<TimeSeries::ITimeSerie>(std::string&, double, double)>;
    PythonInterpreter();
    void add_register_callback(std::function<void(const std::vector<std::pair<std::string,std::vector<std::pair<std::string,std::string>>>>&,
            provider_funct_t)>
            callback);
    ~PythonInterpreter();
    void eval(const std::string& file);
    void release();

private:
};
