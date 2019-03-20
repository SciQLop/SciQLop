#ifndef SCIQLOP_IVARIABLECONTAINER_H
#define SCIQLOP_IVARIABLECONTAINER_H

class Variable2;

/**
 * @brief The IVariableContainer interface represents an UI object that can accommodate a variable
 */
class IVariableContainer
{

public:
    virtual ~IVariableContainer() = default;

    /// Checks if the container can handle the variable passed in parameter
    virtual bool canDrop(Variable2& variable) const = 0;

    /// Checks if the container contains the variable passed in parameter
    virtual bool contains(Variable2& variable) const = 0;
};


#endif // SCIQLOP_IVARIABLECONTAINER_H
