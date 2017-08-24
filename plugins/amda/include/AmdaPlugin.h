#ifndef SCIQLOP_AMDAPLUGIN_H
#define SCIQLOP_AMDAPLUGIN_H

#include "AmdaGlobal.h"

#include <Plugin/IPlugin.h>

#include <QLoggingCategory>

#include <memory>

Q_DECLARE_LOGGING_CATEGORY(LOG_AmdaPlugin)

#ifndef PLUGIN_JSON_FILE_PATH
#define PLUGIN_JSON_FILE_PATH "amda.json"
#endif

class DataSourceItem;

class SCIQLOP_AMDA_EXPORT AmdaPlugin : public QObject, public IPlugin {
    Q_OBJECT
    Q_INTERFACES(IPlugin)
    Q_PLUGIN_METADATA(IID "sciqlop.plugin.IPlugin" FILE PLUGIN_JSON_FILE_PATH)
public:
    /// @sa IPlugin::initialize()
    void initialize() override;
};

#endif // SCIQLOP_AMDAPLUGIN_H
