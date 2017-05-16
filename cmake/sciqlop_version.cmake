#
# sciqlop_version.cmake
#
# Holds the version of sciqlop.
#
# These variables are used to generate the
# "Version.h" and "Version.cpp" files so that the version number is available
# inside of sciqlop source code.
#
# Moreover, they're used with CPack to display the version number in the setups.
#

# Version number parts. These variables must be updated when the version change.
SET (SCIQLOP_VERSION_MAJOR 0)
SET (SCIQLOP_VERSION_MINOR 1)
SET (SCIQLOP_VERSION_PATCH 0)
SET (SCIQLOP_VERSION_SUFFIX "")

# Version number as a string. This variable is automatically generated from the
# above variables to build a version number of the form: MAJOR.MINOR.PATCH. If
# SCIQLOP_VERSION_SUFFIX isn't empty, it is appended to the version number.
SET (SCIQLOP_VERSION "${SCIQLOP_VERSION_MAJOR}.${SCIQLOP_VERSION_MINOR}.${SCIQLOP_VERSION_PATCH}${SCIQLOP_VERSION_SUFFIX}")
