include(ExternalProject)

find_program(meson meson)
find_program(ninja ninja)

SET(SOURCES_PATH ${CMAKE_SOURCE_DIR}/3rdparty/CatalogueAPI)
SET(BUILD_PATH ${CATALOGUEAPI_SOURCES_PATH}/build)
SET(CATALOGUEAPI_QXORM_LIB_PATH ${CATALOGUEAPI_BUILD_PATH}/subprojects/QxOrm)

ExternalProject_Add(
    CatalogueAPI
    GIT_REPOSITORY https://perrinel@hephaistos.lpp.polytechnique.fr/rhodecode/GIT_REPOSITORIES/LPP/Users/mperrinel/CatalogueAPI
    GIT_TAG develop

    SOURCE_DIR ${CMAKE_BINARY_DIR}/CatalogueAPI_src
    BINARY_DIR ${CMAKE_BINARY_DIR}/CatalogueAPI_build
    INSTALL_DIR ${CMAKE_BINARY_DIR}/CatalogueAPI

    CONFIGURE_COMMAND ${meson} --prefix=${CATALOGUEAPI_SOURCES_PATH} --buildtype=${CMAKE_BUILD_TYPE_TOLOWER} "${CATALOGUEAPI_SOURCES_PATH}" "${CATALOGUEAPI_BUILD_PATH}"
    BUILD_COMMAND ${ninja} -C "${CATALOGUEAPI_BUILD_PATH}"
    INSTALL_COMMAND ${ninja} -C "${CATALOGUEAPI_BUILD_PATH}" install

    )
