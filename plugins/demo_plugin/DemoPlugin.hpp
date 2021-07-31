#ifndef SCIQLOP_DEMOPLUGIN_H
#define SCIQLOP_DEMOPLUGIN_H

#include <IPlugin.h>
#include <QtPlugin>

#define PLUGIN_JSON_FILE_PATH "DemoPlugin.json"


class DemoPlugin : public QObject, public IPlugin {
    Q_OBJECT
    Q_INTERFACES(IPlugin)
    Q_PLUGIN_METADATA(IID "sciqlop.plugin.IPlugin" FILE PLUGIN_JSON_FILE_PATH)
public:
    /// @sa IPlugin::initialize()
    void initialize() final;
};

#endif // SCIQLOP_DEMOPLUGIN_H
