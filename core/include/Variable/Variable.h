#ifndef SCIQLOP_VARIABLE_H
#define SCIQLOP_VARIABLE_H

#include <QString>

/**
 * @brief The Variable struct represents a variable in SciQlop.
 */
struct Variable {
    explicit Variable(const QString &name, const QString &unit, const QString &mission)
            : m_Name{name}, m_Unit{unit}, m_Mission{mission}
    {
    }

    QString m_Name;
    QString m_Unit;
    QString m_Mission;
};

#endif // SCIQLOP_VARIABLE_H
