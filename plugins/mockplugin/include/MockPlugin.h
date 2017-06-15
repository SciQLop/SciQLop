#ifndef SCIQLOP_MOCKPLUGIN_H
#define SCIQLOP_MOCKPLUGIN_H

#include <Plugin/IPlugin.h>

#include <QLoggingCategory>

#include <memory>

Q_DECLARE_LOGGING_CATEGORY(LOG_MockPlugin)

class DataSourceItem;

class MockPlugin : public QObject, public IPlugin {
    Q_OBJECT
    Q_INTERFACES(IPlugin)
    Q_PLUGIN_METADATA(IID "sciqlop.plugin.IPlugin" FILE "mockplugin.json")
public:
    /// @sa IPlugin::initialize()
    void initialize() override;
};

#endif // SCIQLOP_MOCKPLUGIN_H
