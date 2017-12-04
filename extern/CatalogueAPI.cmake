# - Clone and build CatalogueAPI Module
include(ExternalProject)

find_package(Git REQUIRED)

if(WIN32)
    find_program(MesonExec meson PATHS C:/Appli/Meson)
    if(NOT MesonExec)
        Message("Error: Meson not found")
    else()
        message("Meson found: ${MesonExec}" )
    endif()
    find_program(NinjaExec ninja PATHS C:/Appli/Meson)
    if(NOT NinjaExec)
        Message("Error: Ninja not found")
    else()
        message("Ninja found: ${NinjaExec}" )
    endif()
endif()
if(NOT MesonExec)
  set (MesonExec meson)
endif()
if(NOT NinjaExec)
    set (NinjaExec ninja)
endif()

SET(CATALOGUEAPI_SOURCES_PATH ${CMAKE_SOURCE_DIR}/3rdparty/CatalogueAPI)
SET(CATALOGUEAPI_BUILD_PATH ${CATALOGUEAPI_SOURCES_PATH}/build)
SET(CATALOGUEAPI_QXORM_LIB_PATH ${CATALOGUEAPI_BUILD_PATH}/subprojects/QxOrm)
SET(CatalogueAPI_build_type plain)

if(CMAKE_BUILD_TYPE STREQUAL "")
    set(CMAKE_BUILD_TYPE Release)
endif()
string(TOLOWER ${CMAKE_BUILD_TYPE} CMAKE_BUILD_TYPE_TOLOWER)

ExternalProject_Add(
    CatalogueAPI

    GIT_REPOSITORY https://perrinel@hephaistos.lpp.polytechnique.fr/rhodecode/GIT_REPOSITORIES/LPP/Users/mperrinel/CatalogueAPI
    GIT_TAG develop

    UPDATE_COMMAND ${GIT_EXECUTABLE} pull
    PATCH_COMMAND ""

    SOURCE_DIR "${CATALOGUEAPI_SOURCES_PATH}"
    CONFIGURE_COMMAND ${MesonExec} --prefix=${CATALOGUEAPI_SOURCES_PATH} --buildtype=${CMAKE_BUILD_TYPE_TOLOWER} "${CATALOGUEAPI_SOURCES_PATH}" "${CATALOGUEAPI_BUILD_PATH}"

    BUILD_COMMAND ${NinjaExec} -C "${CATALOGUEAPI_BUILD_PATH}"
    INSTALL_COMMAND ${NinjaExec} -C "${CATALOGUEAPI_BUILD_PATH}" install
    LOG_DOWNLOAD 1
    LOG_UPDATE 1
)

set(CATALOG_LIB_PATH lib)
if(WIN32)
    set(CATALOG_LIB_PATH bin)
endif()

ExternalProject_Add_Step(
  CatalogueAPI CopyToBin
  COMMAND ${CMAKE_COMMAND} -E copy_directory ${CATALOGUEAPI_SOURCES_PATH}/lib64 ${CATALOGUEAPI_SOURCES_PATH}/${CATALOG_LIB_PATH}
  COMMAND ${CMAKE_COMMAND} -E copy_directory ${CATALOGUEAPI_QXORM_LIB_PATH} ${CATALOGUEAPI_SOURCES_PATH}/${CATALOG_LIB_PATH}
  DEPENDEES install
)


set(CATALOGUEAPI_INCLUDE ${CATALOGUEAPI_SOURCES_PATH}/src)
set(CATALOGUEAPI_LIBRARIES  ${CATALOGUEAPI_SOURCES_PATH}/${CATALOG_LIB_PATH}/${CMAKE_SHARED_LIBRARY_PREFIX}CatalogueAPI${CMAKE_SHARED_LIBRARY_SUFFIX})
list(APPEND CATALOGUEAPI_LIBRARIES ${CATALOGUEAPI_SOURCES_PATH}/${CATALOG_LIB_PATH}/${CMAKE_SHARED_LIBRARY_PREFIX}QxOrm${CMAKE_SHARED_LIBRARY_SUFFIX})

mark_as_advanced(CATALOGUEAPI_INCLUDE)
mark_as_advanced(CATALOGUEAPI_LIBRARIES)
