FILE (GLOB_RECURSE core_SRCS
    ./include/DataSource/DataSourceItemMergeHelper.h
    ./include/DataSource/DataSourceItemAction.h
    ./include/DataSource/DataSourceItem.h
    ./include/DataSource/DataSourceController.h
    ./include/Common/SortUtils.h
    ./include/Common/spimpl.h
    ./include/Common/MimeTypesDef.h
    ./include/Common/MetaTypes.h
    ./include/Common/StringUtils.h
    ./include/Common/SignalWaiter.h
    ./include/Common/DateUtils.h
    ./include/Plugin/IPlugin.h
    ./include/Data/ArrayDataIterator.h
    ./include/Data/VariableRequest.h
    ./include/Data/VectorSeries.h
    ./include/Data/SqpRange.h
    ./include/Data/ScalarSeries.h
    ./include/Data/DataSeriesMergeHelper.h
    ./include/Data/DataSeries.h
    ./include/Data/AcquisitionDataPacket.h
    ./include/Data/DataSeriesType.h
    ./include/Data/AcquisitionRequest.h
    ./include/Data/SqpIterator.h
    ./include/Data/ArrayData.h
    ./include/Data/DataSeriesIterator.h
    ./include/Data/DataSeriesUtils.h
    ./include/Data/SpectrogramSeries.h
    ./include/Data/Unit.h
    ./include/Data/DataProviderParameters.h
    ./include/Data/OptionalAxis.h
    ./include/Data/IDataProvider.h
    ./include/Data/IDataSeries.h
    ./include/Network/NetworkController.h
    ./include/Version.h
    ./include/CoreGlobal.h
    ./include/Catalogue/CatalogueController.h
    ./include/Visualization/VisualizationController.h
    ./include/PluginManager/PluginManager.h
    ./include/Variable/VariableModel.h
    ./include/Variable/VariableAcquisitionWorker.h
    ./include/Variable/VariableCacheStrategy.h
    ./include/Variable/VariableSynchronizationGroup.h
    ./include/Variable/VariableSingleThresholdCacheStrategy.h
    ./include/Variable/VariableCacheStrategyFactory.h
    ./include/Variable/Variable.h
    ./include/Variable/VariableCacheController.h
    ./include/Variable/VariableController.h
    ./include/Time/TimeController.h
    ./include/Settings/ISqpSettingsBindable.h
    ./include/Settings/SqpSettingsDefs.h

    ./src/DataSource/DataSourceItem.cpp
    ./src/DataSource/DataSourceItemAction.cpp
    ./src/DataSource/DataSourceItemMergeHelper.cpp
    ./src/DataSource/DataSourceController.cpp
    ./src/Common/DateUtils.cpp
    ./src/Common/MimeTypesDef.cpp
    ./src/Common/StringUtils.cpp
    ./src/Common/SignalWaiter.cpp
    ./src/Data/ScalarSeries.cpp
    ./src/Data/DataSeriesIterator.cpp
    ./src/Data/OptionalAxis.cpp
    ./src/Data/ArrayDataIterator.cpp
    ./src/Data/SpectrogramSeries.cpp
    ./src/Data/DataSeriesUtils.cpp
    ./src/Data/VectorSeries.cpp
    ./src/Network/NetworkController.cpp
    ./src/Catalogue/CatalogueController.cpp
    ./src/Visualization/VisualizationController.cpp
    ./src/PluginManager/PluginManager.cpp
    ./src/Variable/VariableController.cpp
    ./src/Variable/VariableModel.cpp
    ./src/Variable/VariableCacheController.cpp
    ./src/Variable/VariableSynchronizationGroup.cpp
    ./src/Variable/Variable.cpp
    ./src/Variable/VariableAcquisitionWorker.cpp
    ./src/Version.cpp
    ./src/Time/TimeController.cpp
    ./src/Settings/SqpSettingsDefs.cpp

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
  catalogs
)


pybind11_add_module(sciqlopqt src/pybind11_wrappers/QtWrappers.cpp)
target_link_libraries(sciqlopqt PUBLIC Qt5::Core)

pybind11_add_module(pysciqlopcore src/pybind11_wrappers/CoreWrappers.cpp)
target_link_libraries(pysciqlopcore PUBLIC sciqlopcore)

add_library(pysciqlop src/pybind11_wrappers/pywrappers_common.h)
target_link_libraries(pysciqlop PUBLIC Qt5::Core)
target_include_directories(pysciqlop PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/src/pybind11_wrappers/>
    $<INSTALL_INTERFACE:include/SciQLOP/py_wrappers>
)

SET_PROPERTY(GLOBAL PROPERTY CORE_PYTHON_PATH  ${CMAKE_CURRENT_BINARY_DIR})


install(TARGETS sciqlopcore EXPORT SciQLOPCoreConfig
    ARCHIVE  DESTINATION ${CMAKE_INSTALL_LIBDIR}
    LIBRARY  DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME  DESTINATION ${CMAKE_INSTALL_BINDIR})

install(DIRECTORY include/ DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}/SciQLOP)
install(EXPORT SciQLOPCoreConfig DESTINATION share/SciQLOPCore/cmake)
export(TARGETS sciqlopcore FILE SciQLOPCoreConfig.cmake)

add_subdirectory(tests)
