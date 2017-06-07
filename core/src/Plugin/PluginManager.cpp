#include <Plugin/PluginManager.h>

#include <Plugin/IPlugin.h>

#include <QDir>
#include <QLibrary>
#include <QPluginLoader>

Q_LOGGING_CATEGORY(LOG_PluginManager, "PluginManager")

namespace {

/// Key for retrieving metadata of the plugin
const auto PLUGIN_METADATA_KEY = QStringLiteral("MetaData");

/// Key for retrieving the name of the plugin in its metadata
const auto PLUGIN_NAME_KEY = QStringLiteral("name");

} // namespace

struct PluginManager::PluginManagerPrivate {
    /**
     * Loads a single plugin into SciQlop. The method has no effect if the plugin is malformed (e.g.
     * wrong library type, missing metadata, etc.)
     * @param pluginPath the path to the plugin library.
     */
    void loadPlugin(const QString &pluginPath)
    {
        qCDebug(LOG_PluginManager())
            << QObject::tr("Attempting to load file '%1' as a plugin").arg(pluginPath);

        if (QLibrary::isLibrary(pluginPath)) {
            QPluginLoader pluginLoader{pluginPath};

            // Retrieving the plugin name to check if it can be loaded (i.e. no plugin with the same
            // name has been registered yet)
            auto metadata = pluginLoader.metaData().value(PLUGIN_METADATA_KEY).toObject();
            auto pluginName = metadata.value(PLUGIN_NAME_KEY).toString();

            if (pluginName.isEmpty()) {
                /// @todo ALX : log error
            }
            else if (m_RegisteredPlugins.contains(pluginName)) {
                /// @todo ALX : log error
            }
            else {
                if (auto pluginInstance = qobject_cast<IPlugin *>(pluginLoader.instance())) {
                    pluginInstance->initialize();
                    m_RegisteredPlugins.insert(pluginName, pluginPath);
                }
                else {
                    /// @todo ALX : log error
                }
            }
        }
        else {
            /// @todo ALX : log error
        }
    }

    /// Registered plugins (key: plugin name, value: plugin path)
    QHash<QString, QString> m_RegisteredPlugins;
};

PluginManager::PluginManager() : impl{spimpl::make_unique_impl<PluginManagerPrivate>()}
{
}

void PluginManager::loadPlugins(const QDir &pluginDir)
{
    // Load plugins
    auto pluginInfoList = pluginDir.entryInfoList(QDir::Files, QDir::Name);
    for (auto pluginInfo : qAsConst(pluginInfoList)) {
        impl->loadPlugin(pluginInfo.absoluteFilePath());
    }
}

int PluginManager::nbPluginsLoaded() const noexcept
{
    /// @todo ALX
    return 0;
}
