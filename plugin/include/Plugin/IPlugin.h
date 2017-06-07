#ifndef SCIQLOP_IPLUGIN_H
#define SCIQLOP_IPLUGIN_H

#include <QString>
#include <QtPlugin>

/**
 * @brief Interface for a plugin
 */
class IPlugin {
public:
    virtual ~IPlugin() = default;

    /// Initializes the plugin
    virtual void initialize() = 0;
};

Q_DECLARE_INTERFACE(IPlugin, "sciqlop.plugin.IPlugin")

#endif // SCIQLOP_IPLUGIN_H
