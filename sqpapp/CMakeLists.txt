
## sciqlop - CMakeLists.txt
SET(EXECUTABLE_NAME "sciqlop")
SET(SOURCES_DIR ${CMAKE_CURRENT_SOURCE_DIR}/src/)
SET(INCLUDE_FOLDER ${CMAKE_CURRENT_SOURCE_DIR}/include)
SET(UI_FOLDER ${CMAKE_CURRENT_SOURCE_DIR}/src)
SET(RES_FOLDER ${CMAKE_CURRENT_SOURCE_DIR}/resources)

#
# Find Qt modules
#
SCIQLOP_FIND_QT(Core Widgets)
	
#
# Find dependent libraries
# ========================
SET(LIBRARIES)
SET(EXTERN_LIBRARIES)
SET(EXTERN_SHARED_LIBRARIES)

# Add sqpcore to the list of libraries to use
list(APPEND LIBRARIES ${SQPCORE_LIBRARY_NAME})

# Include sqpcore directory
include_directories("${CMAKE_CURRENT_SOURCE_DIR}/../sqpcore/src")

# Add dependent shared libraries
list(APPEND SHARED_LIBRARIES ${SQPCORE_SHARED_LIBRARIES})

# Retrieve the location of the dynamic library to copy it to the output path
get_property(sqpcoreLocation TARGET ${SQPCORE_LIBRARY_NAME} PROPERTY LOCATION)
list(APPEND SHARED_LIBRARIES_FROM_TARGETS ${sqpcoreLocation})

#
# Compile the application
#
FILE (GLOB_RECURSE APPLICATION_SOURCES
	${SOURCES_DIR}/*.c
	${SOURCES_DIR}/*.cpp
	${SOURCES_DIR}/*.h)

# Headers files (.h)
FILE (GLOB_RECURSE PROJECT_HEADERS ${INCLUDE_FOLDER}/*.h)

# Ui files
FILE (GLOB_RECURSE PROJECT_FORMS ${UI_FOLDER}/*.ui)

# Resources files
FILE (GLOB_RECURSE PROJECT_RESOURCES ${RES_FOLDER}/*.qrc)
	
# Retrieve resources files
FILE (GLOB_RECURSE APPLICATION_RESOURCES ${RES_FOLDER}/*.qrc)

QT5_ADD_RESOURCES(RCC_HDRS ${APPLICATION_RESOURCES} )

QT5_WRAP_UI(UIS_HDRS
 ${PROJECT_FORMS}
)


ADD_EXECUTABLE(${EXECUTABLE_NAME} ${APPLICATION_SOURCES} ${RCC_HDRS} ${UIS_HDRS})
target_link_libraries(${EXECUTABLE_NAME}
    ${LIBRARIES})
	
# Link with Qt5 modules
qt5_use_modules(${EXECUTABLE_NAME} Core Widgets)
		
		
# Add the files to the list of files to be analyzed
LIST(APPEND CHECKSTYLE_INPUT_FILES ${APPLICATION_SOURCES})
SCIQLOP_SET_TO_PARENT_SCOPE(CHECKSTYLE_INPUT_FILES)
# Vera++ exclusion files
#LIST(APPEND CHECKSTYLE_EXCLUSION_FILES ${CMAKE_CURRENT_SOURCE_DIR}/path/to/exclusionFiles.tcl)
SCIQLOP_SET_TO_PARENT_SCOPE(CHECKSTYLE_EXCLUSION_FILES)

#
# Compile the tests
#
IF(BUILD_TESTS)
	INCLUDE_DIRECTORIES(${SOURCES_DIR})
	FILE (GLOB_RECURSE TESTS_SOURCES ${CMAKE_CURRENT_SOURCE_DIR}/Test*.cpp)
	FILE (GLOB_RECURSE TESTS_HEADERS ${CMAKE_CURRENT_SOURCE_DIR}/Test*.h)
	SET( TEST_LIBRARIES ${LIBRARIES} ${EXTERN_LIBRARIES})

	FOREACH( testFile ${TESTS_SOURCES} )
		GET_FILENAME_COMPONENT( testDirectory ${testFile} DIRECTORY )
		GET_FILENAME_COMPONENT( testName ${testFile} NAME_WE )

		# Add to the list of sources files all the sources in the same
		# directory that aren't another test
		FILE (GLOB currentTestSources
			${testDirectory}/*.c
			${testDirectory}/*.cpp
			${testDirectory}/*.h)
		LIST (REMOVE_ITEM currentTestSources ${TESTS_SOURCES})
		LIST (REMOVE_ITEM currentTestSources ${TESTS_HEADERS})

		ADD_EXECUTABLE(${testName} ${testFile} ${currentTestSources})
		TARGET_LINK_LIBRARIES( ${testName} ${TEST_LIBRARIES} )
		qt5_use_modules(${testName} Test)

		ADD_TEST( NAME ${testName} COMMAND ${testName} )

                SCIQLOP_COPY_TO_TARGET(RUNTIME ${testName} ${EXTERN_SHARED_LIBRARIES})
	ENDFOREACH( testFile )

	LIST(APPEND testFilesToFormat ${TESTS_SOURCES})
	LIST(APPEND testFilesToFormat ${TESTS_HEADERS})
	LIST(APPEND FORMATTING_INPUT_FILES ${testFilesToFormat})
        SCIQLOP_SET_TO_PARENT_SCOPE(FORMATTING_INPUT_FILES)
ENDIF(BUILD_TESTS)

#
# Set the files that must be formatted by clang-format.
#
LIST (APPEND FORMATTING_INPUT_FILES ${APPLICATION_SOURCES})
SCIQLOP_SET_TO_PARENT_SCOPE(FORMATTING_INPUT_FILES)

# 
# Set the directories that doxygen must browse to generate the 
# documentation.
# 
# Source directories:
LIST (APPEND DOXYGEN_INPUT_DIRS "${CMAKE_CURRENT_SOURCE_DIR}/docs")
LIST (APPEND DOXYGEN_INPUT_DIRS "${CMAKE_CURRENT_SOURCE_DIR}/src")
SCIQLOP_SET_TO_PARENT_SCOPE(DOXYGEN_INPUT_DIRS)
# Source directories to exclude from the documentation generation
#LIST (APPEND DOXYGEN_EXCLUDE_PATTERNS "${CMAKE_CURRENT_SOURCE_DIR}/path/to/subdir/*")
SCIQLOP_SET_TO_PARENT_SCOPE(DOXYGEN_EXCLUDE_PATTERNS)

# 
# Set the directories with the sources to analyze and propagate the 
# modification to the parent scope
# 
# Source directories to analyze: 
LIST (APPEND ANALYSIS_INPUT_DIRS "${CMAKE_CURRENT_SOURCE_DIR}/src")
LIST (APPEND ANALYSIS_INPUT_DIRS "${CMAKE_CURRENT_SOURCE_DIR}/tests")
SCIQLOP_SET_TO_PARENT_SCOPE(ANALYSIS_INPUT_DIRS)
# Source directories to exclude from the analysis
#LIST (APPEND ANALYSIS_EXCLUDE_DIRS "${CMAKE_CURRENT_SOURCE_DIR}/path/to/subdir")
SCIQLOP_SET_TO_PARENT_SCOPE(ANALYSIS_EXCLUDE_DIRS)
