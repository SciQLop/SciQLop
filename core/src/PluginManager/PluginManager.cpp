#include <PluginManager/PluginManager.h>

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

/// Helper to state the plugin loading operation
struct LoadPluginState {
    explicit LoadPluginState(const QString &pluginPath)
            : m_PluginPath{pluginPath}, m_Valid{true}, m_ErrorMessage{}
    {
    }

    void log() const
    {
        if (m_Valid) {
            qCDebug(LOG_PluginManager())
                << QObject::tr("File '%1' has been loaded as a plugin").arg(m_PluginPath);
        }
        else {
            qCWarning(LOG_PluginManager())
                << QObject::tr("File '%1' can't be loaded as a plugin: %2")
                       .arg(m_PluginPath)
                       .arg(m_ErrorMessage);
        }
    }

    void setError(const QString &errorMessage)
    {
        m_Valid = false;
        m_ErrorMessage = errorMessage;
    }

    QString m_PluginPath;
    bool m_Valid;
    QString m_ErrorMessage;
};

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

        LoadPluginState loadState{pluginPath};

        if (QLibrary::isLibrary(pluginPath)) {
            QPluginLoader pluginLoader{pluginPath};

            // Retrieving the plugin name to check if it can be loaded (i.e. no plugin with the same
            // name has been registered yet)
            auto metadata = pluginLoader.metaData().value(PLUGIN_METADATA_KEY).toObject();
            auto pluginName = metadata.value(PLUGIN_NAME_KEY).toString();

            if (pluginName.isEmpty()) {
                loadState.setError(QObject::tr("empty file name"));
            }
            else if (m_RegisteredPlugins.contains(pluginName)) {
                loadState.setError(QObject::tr("name '%1' already registered").arg(pluginName));
            }
            else {
                if (auto pluginInstance = qobject_cast<IPlugin *>(pluginLoader.instance())) {
                    pluginInstance->initialize();
                    m_RegisteredPlugins.insert(pluginName, pluginPath);
                }
                else {
                    loadState.setError(QObject::tr("the file is not a Sciqlop plugin"));
                }
            }
        }
        else {
            loadState.setError(QObject::tr("the file is not a library"));
        }

        // Log loading result
        loadState.log();
    }

    void loadStaticPlugins()
    {
        for (QObject *plugin : QPluginLoader::staticInstances()) {
            qobject_cast<IPlugin *>(plugin)->initialize();
            m_RegisteredPlugins.insert(plugin->metaObject()->className(), "StaticPlugin");
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
    auto pluginInfoList
        = pluginDir.entryInfoList(QDir::Files | QDir::Dirs | QDir::NoDotAndDotDot, QDir::Name);
    for (auto entryInfo : qAsConst(pluginInfoList)) {
        if (entryInfo.isDir()) {
            this->loadPlugins(QDir{entryInfo.absoluteFilePath()});
        }
        else if (QLibrary::isLibrary(entryInfo.absoluteFilePath())) {
            impl->loadPlugin(entryInfo.absoluteFilePath());
        }
    }
}

void PluginManager::loadStaticPlugins()
{
    impl->loadStaticPlugins();
}

int PluginManager::nbPluginsLoaded() const noexcept
{
    return impl->m_RegisteredPlugins.size();
}
