#include <TimeSeries.h>
#include <functional>
#include <iostream>
#include <memory>


class PythonInterpreter
{
public:
    using provider_funct_t = std::function<std::shared_ptr<TimeSeries::ITimeSerie>(
        std::vector<std::tuple<std::string, std::string>>&, double, double)>;
    using product_t = std::tuple<std::string, std::vector<std::string>,
        std::vector<std::pair<std::string, std::string>>>;

    PythonInterpreter();
    void add_register_callback(
        std::function<void(const std::vector<product_t>&, provider_funct_t)> callback);
    ~PythonInterpreter();
    void eval(const std::string& file);
    void eval_str(const std::string &content);
    void release();

private:
};
