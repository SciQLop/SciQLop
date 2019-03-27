#include <Data/DateTimeRange.h>
#include <TimeSeries.h>
#include <functional>
#include <iostream>
#include <memory>


class PythonInterpreter
{
public:
    PythonInterpreter();
    void add_register_callback(std::function<void(const std::vector<std::string>&,
            std::function<std::shared_ptr<TimeSeries::ITimeSerie>(std::string&, double, double)>)>
            callback);
    ~PythonInterpreter();
    void eval(const std::string& file);

private:
};
