#ifndef SCIQLOP_ISQPSETTINGSBINDABLE_H
#define SCIQLOP_ISQPSETTINGSBINDABLE_H

#include <QSettings>

/**
 * @brief The ISqpSettingsBindable interface represents an object that can bind a variable
 */
class ISqpSettingsBindable {

public:
    virtual ~ISqpSettingsBindable() = default;

    /// Loads settings into the object
    virtual void loadSettings() = 0;

    /// Saves settings from the object
    virtual void saveSettings() const = 0;
};

#endif // SCIQLOP_ISQPSETTINGSBINDABLE_H
