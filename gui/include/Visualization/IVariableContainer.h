#ifndef SCIQLOP_IVARIABLECONTAINER_H
#define SCIQLOP_IVARIABLECONTAINER_H

class Variable;

/**
 * @brief The IVariableContainer interface represents an UI object that can accommodate a variable
 */
class IVariableContainer {

public:
    virtual ~IVariableContainer() = default;

    /// Checks if the container can handle the variable passed in parameter
    virtual bool canDrop(const Variable &variable) const = 0;
};


#endif // SCIQLOP_IVARIABLECONTAINER_H
