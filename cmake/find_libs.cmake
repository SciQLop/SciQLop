#
# findslibs.cmake
#

#
# Qt
#
# Find Qt here so that a message is displayed in the console when executing
# cmake, but each application must call SCIQLOP_FIND_QT() to load the Qt modules that
# it needs.
FIND_PACKAGE(Qt5Core REQUIRED)
FIND_PACKAGE(Qt5Test REQUIRED)
FIND_PACKAGE(Qt5Gui REQUIRED)

#
# doxygen tools
#
FIND_PACKAGE(Doxygen)

# 
# Cppcheck tool
#
FIND_PACKAGE(cppcheck)

#
# Formatting tools
#
LIST( APPEND CMAKE_MODULE_PATH "${CMAKE_SOURCE_DIR}/formatting/cmake")
FIND_PACKAGE(vera++)
FIND_PACKAGE(ClangFormat)
