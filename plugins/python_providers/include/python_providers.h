#ifndef PYTHON_PROVIDERS_H
#define PYTHON_PROVIDERS_H

#include <Plugin/IPlugin.h>


#include <memory>

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
};

#endif // PYTHON_PROVIDERS_H
