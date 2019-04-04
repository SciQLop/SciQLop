#ifndef PYTHON_PROVIDERS_H
#define PYTHON_PROVIDERS_H

#include <Plugin/IPlugin.h>
#include <QUuid>

#include <memory>
#include <python_interpreter.h>

#ifndef SCIQLOP_PLUGIN_JSON_FILE_PATH
#define SCIQLOP_PLUGIN_JSON_FILE_PATH "python_providers.json"
#endif

class DataSourceItem;

class PythonProviders : public QObject, public IPlugin
{
    Q_OBJECT
    Q_INTERFACES(IPlugin)
    Q_PLUGIN_METADATA(IID "sciqlop.plugin.IPlugin" FILE SCIQLOP_PLUGIN_JSON_FILE_PATH)
public:
    /// @sa IPlugin::initialize()
    void initialize() override;
    ~PythonProviders();

private:
    void register_product(const std::vector<PythonInterpreter::product_t>& product_list,
        PythonInterpreter::provider_funct_t f);
    PythonInterpreter _interpreter;
};

#endif // PYTHON_PROVIDERS_H
