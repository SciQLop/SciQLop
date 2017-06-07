#include <Plugin/PluginManager.h>

#include <Plugin/IPlugin.h>

#include <QDir>

Q_LOGGING_CATEGORY(LOG_PluginManager, "PluginManager")

struct PluginManager::PluginManagerPrivate {
};

PluginManager::PluginManager() : impl{spimpl::make_unique_impl<PluginManagerPrivate>()}
{
}

void PluginManager::loadPlugins(const QDir &pluginDir)
{
    // Load plugins
    auto pluginInfoList = pluginDir.entryInfoList(QDir::Files, QDir::Name);
    for (auto pluginInfo : qAsConst(pluginInfoList)) {
        /// @todo ALX
    }
}

int PluginManager::nbPluginsLoaded() const noexcept
{
    /// @todo ALX
    return 0;
}
