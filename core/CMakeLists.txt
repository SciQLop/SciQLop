FILE (GLOB_RECURSE core_SRCS
        include/*.h
        src/*.cpp
        )

add_definitions(-DCORE_STATIC)

add_library(sciqlopcore ${core_SRCS})
SET_TARGET_PROPERTIES(sciqlopcore PROPERTIES WINDOWS_EXPORT_ALL_SYMBOLS TRUE)

target_include_directories(sciqlopcore PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include/SciQLOP>
)

target_link_libraries(sciqlopcore PUBLIC
  Qt5::Core
  Qt5::Network
  CatalogueAPI
)

install(TARGETS sciqlopcore EXPORT SciQLOPCoreConfig
    ARCHIVE  DESTINATION ${CMAKE_INSTALL_LIBDIR}
    LIBRARY  DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME  DESTINATION ${CMAKE_INSTALL_BINDIR})

install(DIRECTORY include/ DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}/SciQLOP)
install(EXPORT SciQLOPCoreConfig DESTINATION share/SciQLOPCore/cmake)
export(TARGETS sciqlopcore FILE SciQLOPCoreConfig.cmake)

add_subdirectory(tests)
