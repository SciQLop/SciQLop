from PySide6.QtCore import QObject, Signal, Slot, Property


class SciQLopProperty(Property):
    def __init__(self, *args, **kwargs):
        Property.__init__(self, *args, **kwargs)

    def __set_name__(self, owner, name):
        if not hasattr(owner, "_sciqlop_attributes_"):
            owner._sciqlop_attributes_ = set()
        owner._sciqlop_attributes_.add(name)

