# - Try to find CatalogueAPI Module
# Once done this will define
#  CATALOGUEAPI_FOUND - System has CatalogueAPI
#  CATALOGUEAPI_INCLUDE_DIRS - The CatalogueAPI include directories
#  CATALOGUEAPI_LIBRARIES - The libraries needed to use CatalogueAPI
#  CATALOGUEAPI_SHARED_LIBRARIES - The shared libraries for CatalogueAPI

set(CATALOGUEAPI_ROOT_DIR "${CATALOGUEAPI_EXTERN_FOLDER}"
    CACHE PATHS
    "Path to the installation of CatalogueAPI"
    ${libRootDirForceValue})

find_path(CATALOGUEAPI_INCLUDE_DIR CatalogueDao.h
          HINTS ${CATALOGUEAPI_ROOT_DIR} ${CATALOGUEAPI_EXTERN_FOLDER}
          PATH_SUFFIXES src )

find_library(CATALOGUEAPI_LIBRARY NAMES CatalogueAPI
             HINTS ${CATALOGUEAPI_ROOT_DIR} ${CATALOGUEAPI_EXTERN_FOLDER}
             PATH_SUFFIXES lib)

set(CATALOGUEAPI_LIBRARIES ${CATALOGUEAPI_LIBRARY} )
set(CATALOGUEAPI_INCLUDE_DIRS ${CATALOGUEAPI_INCLUDE_DIR} )

include(FindPackageHandleStandardArgs)
# handle the QUIETLY and REQUIRED arguments and set CATALOGUEAPI_FOUND to TRUE
# if all listed variables are TRUE
find_package_handle_standard_args(CatalogueAPI FOUND_VAR CATALOGUEAPI_FOUND
                                         REQUIRED_VARS CATALOGUEAPI_LIBRARY CATALOGUEAPI_INCLUDE_DIR)
mark_as_advanced(CATALOGUEAPI_INCLUDE_DIR CATALOGUEAPI_LIBRARY )
