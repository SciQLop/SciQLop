#ifndef SCIQLOP_MOCKPLUGIN_H
#define SCIQLOP_MOCKPLUGIN_H

#include "MockPluginGlobal.h"

#include <Plugin/IPlugin.h>

#include <QLoggingCategory>

#include <memory>

#ifndef PLUGIN_JSON_FILE_PATH
#define PLUGIN_JSON_FILE_PATH "mockplugin.json"
#endif

Q_DECLARE_LOGGING_CATEGORY(LOG_MockPlugin)

class DataSourceItem;

class SCIQLOP_MOCKPLUGIN_EXPORT MockPlugin : public QObject, public IPlugin {
    Q_OBJECT
    Q_INTERFACES(IPlugin)
    Q_PLUGIN_METADATA(IID "sciqlop.plugin.IPlugin" FILE PLUGIN_JSON_FILE_PATH)
public:
    /// @sa IPlugin::initialize()
    void initialize() override;
};

#endif // SCIQLOP_MOCKPLUGIN_H
