#ifndef SCIQLOP_PLUGINMANAGER_H
#define SCIQLOP_PLUGINMANAGER_H

#include "CoreGlobal.h"

#include <Common/spimpl.h>

#include <QLoggingCategory>

class QDir;

Q_DECLARE_LOGGING_CATEGORY(LOG_PluginManager)

/**
 * @brief The PluginManager class aims to handle the plugins loaded dynamically into SciQLop.
 */
class  PluginManager {
public:
    explicit PluginManager();

    /**
     * Loads plugins into SciQlop. The loaded plugins are those located in the directory passed in
     * parameter
     * @param pluginDir the directory containing the plugins
     */
    void loadPlugins(const QDir &pluginDir);

    /**
     * Loads static plugins into SciQlop. SciQLOP supports statically linked plugins.
     */
    void loadStaticPlugins();

    /// @returns the number of plugins loaded
    int nbPluginsLoaded() const noexcept;

private:
    struct PluginManagerPrivate;
    spimpl::unique_impl_ptr<PluginManagerPrivate> impl;
};

#endif // SCIQLOP_PLUGINMANAGER_H
