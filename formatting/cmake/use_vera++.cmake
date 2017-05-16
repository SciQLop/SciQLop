# 
# use_vera++.cmake
# 
# The following functions are defined in this document:
#   - ADD_VERA_TARGETS
#   - ADD_VERA_CHECKSTYLE_TARGET
# 

# ADD_VERA_TARGETS(<globExpression> ... 
#   [ADD_TO_ALL]
#   [NAME <name>]
#   [NAME_ALL <nameall>]
#   [ROOT <directory>]
#   [PROFILE <profile>]
#   [RECURSE]
#   [EXCLUSION <exclusionFile> ...]
#   [PARAMETER <name>=<value> ...]
#   [PARAMETERFILE <parameterFile> ...])
#   
# Two custom targets will be created:
# * style_reports is run as part of the build, and is not rerun unless one of
# the file checked is modified (only created if ADD_TO_ALL is provided);
# * style must be explicitely called (make style) and is rerun even if the files
# to check have not been modified. To achieve this behavior, the commands used
# in this target pretend to produce a file without actually producing it.
# Because the output file is not there after the run, the command will be rerun
# again at the next target build.
# The report style is selected based on the build environment, so the style
# problems are properly reported in the IDEs
# 
# If ADD_TO_ALL is provided then a target will be added to the default build
# targets so that each time a source file is compiled, it is analyzed with
# vera++.
#
# NAME and NAME_ALL customize the name of the targets (style and style_reports 
# by default respectively).
# 
# ROOT set the vera++ root directory, containing the rules and profiles (default 
# to the current binary directory).
# 
# PROFILE selects the vera++ profile to use (default to "default").
# 
# RECURSE selects if the glob expressions should be applied recursively or not.
# 
# EXCLUSION list of vera++ exclusion files. Can be used several times.
# 
# PARAMETER list of vera++ parameters (name=value). Can be used several times.
# 
# PARAMETERFILE list of vera++ parameter files. Can be used several times.
function(add_vera_targets)
  # default values
  set(target "style")
  set(target_all "style_reports")
  set(profile "default")
  set(root "${CMAKE_CURRENT_BINARY_DIR}")
  set(exclusions)
  set(parameters)
  set(parameterFiles)
  set(recurse OFF)
  set(addToAll OFF)
  set(globs)
  # parse the options
  math(EXPR lastIdx "${ARGC} - 1")
  set(i 0)
  while(i LESS ${ARGC})
    set(arg "${ARGV${i}}")
    if("${arg}" STREQUAL "ADD_TO_ALL")
      set(addToAll ON)
    elseif("${arg}" STREQUAL "NAME")
      vera_incr(i)
      set(target "${ARGV${i}}")
    elseif("${arg}" STREQUAL "NAME_ALL")
      vera_incr(i)
      set(target_all "${ARGV${i}}")
    elseif("${arg}" STREQUAL "ROOT")
      vera_incr(i)
      set(root "${ARGV${i}}")
    elseif("${arg}" STREQUAL "PROFILE")
      vera_incr(i)
      set(profile "${ARGV${i}}")
    elseif("${arg}" STREQUAL "EXCLUSION")
      vera_incr(i)
      list(APPEND exclusions --exclusions "${ARGV${i}}")
    elseif("${arg}" STREQUAL "RECURSE")
      set(recurse ON)
    elseif("${arg}" STREQUAL "PARAMETER")
      vera_incr(i)
      list(APPEND parameters --parameter "${ARGV${i}}")
    elseif("${arg}" STREQUAL "PARAMETERFILE")
      vera_incr(i)
      list(APPEND parameterFiles --parameters "${ARGV${i}}")
    else()
      list(APPEND globs ${arg})
    endif()
    vera_incr(i)
  endwhile()

  if(recurse)
    file(GLOB_RECURSE srcs ${globs})
  else()
    file(GLOB srcs ${globs})
  endif()
  list(SORT srcs)

  if(NOT VERA++_EXECUTABLE AND TARGET vera)
    set(vera_program "$<TARGET_FILE:vera>")
  else()
    set(vera_program "${VERA++_EXECUTABLE}")
  endif()

  # Two custom targets will be created:
  # * style_reports is run as part of the build, and is not rerun unless one of
  # the file checked is modified;
  # * style must be explicitely called (make style) and is rerun even if the files
  # to check have not been modified. To achieve this behavior, the commands used
  # in this target pretend to produce a file without actually producing it.
  # Because the output file is not there after the run, the command will be rerun
  # again at the next target build.
  # The report style is selected based on the build environment, so the style
  # problems are properly reported in the IDEs
  if(MSVC)
    set(style vc)
  else()
    set(style std)
  endif()
  set(xmlreports)
  set(noreports)
  set(reportNb 0)
  set(reportsrcs)
  list(GET srcs 0 first)
  get_filename_component(currentDir ${first} PATH)
  # add a fake src file in a fake dir to trigger the creation of the last
  # custom command
  list(APPEND srcs "#12345678900987654321#/0987654321#1234567890")
  # Create the directory where the reports will be saved
  SET(reportDirectory "${CMAKE_CURRENT_BINARY_DIR}/vera")
  FILE(MAKE_DIRECTORY ${reportDirectory})
  foreach(s ${srcs})
    get_filename_component(d ${s} PATH)
    if(NOT "${d}" STREQUAL "${currentDir}")
      # this is a new dir - lets generate everything needed for the previous dir
      string(LENGTH "${CMAKE_SOURCE_DIR}" len)
      string(SUBSTRING "${currentDir}" 0 ${len} pre)
      if("${pre}" STREQUAL "${CMAKE_SOURCE_DIR}")
        string(SUBSTRING "${currentDir}" ${len} -1 currentDir)
        string(REGEX REPLACE "^/" "" currentDir "${currentDir}")
      endif()
      if("${currentDir}" STREQUAL "")
        set(currentDir ".")
      endif()
      set(xmlreport ${reportDirectory}/vera_report_${reportNb}.xml)
      if(addToAll)
        add_custom_command(
          OUTPUT ${xmlreport}
          COMMAND ${vera_program}
            --root ${root}
            --profile ${profile}
            --${style}-report=-
            --show-rule
            --warning
            --xml-report=${xmlreport}
            ${exclusions}
            ${parameters}
            ${parameterFiles}
            ${reportsrcs}
          DEPENDS ${reportsrcs}
          COMMENT "Checking style with vera++ in ${currentDir}"
        )
      endif()

      set(noreport ${reportDirectory}/vera_noreport_${reportNb}.xml)
      add_custom_command(
        OUTPUT ${noreport}
        COMMAND ${vera_program}
          --root ${root}
          --profile ${profile}
          --${style}-report=-
          --show-rule
          --warning
          # --xml-report=${noreport}
          ${exclusions}
          ${parameters}
          ${parameterFiles}
          ${reportsrcs}
        DEPENDS ${reportsrcs}
        COMMENT "Checking style with vera++ in ${currentDir}"
      )

      list(APPEND xmlreports ${xmlreport})
      list(APPEND noreports ${noreport})
      vera_incr(reportNb)
      # clear the list for the next dir
      set(reportsrcs)
      set(currentDir ${d})
    endif()
    list(APPEND reportsrcs ${s})
  endforeach()
  # Create the custom targets that will trigger the custom command created
  # previously
  if(addToAll)
    add_custom_target(${target_all} ALL DEPENDS ${xmlreports})
  endif()
  add_custom_target(${target} DEPENDS ${noreports})
endfunction()


# ADD_VERA_CHECKSTYLE_TARGET(<globExpression> ... 
#   [NAME <name>]
#   [ROOT <directory>]
#   [PROFILE <profile>]
#   [RECURSE]
#   [EXCLUSION <exclusionFile> ...]
#   [PARAMETER <name>=<value> ...]
#   [PARAMETERFILE <parameterFile> ...])
#   
# The checkstyle custom target will be created. This target runs vera++ and 
# create checkstyle reports in the ${CMAKE_CURRENT_BINARY_DIR}/checkstyle 
# directory.
# 
# NAME customize the name of the target (checkstyle by default).
# 
# ROOT set the vera++ root directory, containing the rules and profiles (default 
# to the current binary directory).
# 
# PROFILE selects the vera++ profile to use (default to "default").
# 
# RECURSE selects if the glob expressions should be applied recursively or not.
# 
# EXCLUSION list of vera++ exclusion files. Can be used several times.
# 
# PARAMETER list of vera++ parameters (name=value). Can be used several times.
# 
# PARAMETERFILE list of vera++ parameter files. Can be used several times.
function(add_vera_checkstyle_target)
  # default values
  set(target "checkstyle")
  set(profile "default")
  set(root "${CMAKE_CURRENT_BINARY_DIR}")
  set(exclusions)
  set(parameters)
  set(parameterFiles)
  set(recurse OFF)
  set(globs)
  # parse the options
  math(EXPR lastIdx "${ARGC} - 1")
  set(i 0)
  while(i LESS ${ARGC})
    set(arg "${ARGV${i}}")
    if("${arg}" STREQUAL "NAME")
      vera_incr(i)
      set(target "${ARGV${i}}")
    elseif("${arg}" STREQUAL "ROOT")
      vera_incr(i)
      set(root "${ARGV${i}}")
    elseif("${arg}" STREQUAL "PROFILE")
      vera_incr(i)
      set(profile "${ARGV${i}}")
    elseif("${arg}" STREQUAL "EXCLUSION")
      vera_incr(i)
      list(APPEND exclusions --exclusions "${ARGV${i}}")
    elseif("${arg}" STREQUAL "RECURSE")
      set(recurse ON)
    elseif("${arg}" STREQUAL "PARAMETER")
      vera_incr(i)
      list(APPEND parameters --parameter "${ARGV${i}}")
    elseif("${arg}" STREQUAL "PARAMETERFILE")
      vera_incr(i)
      list(APPEND parameterFiles --parameters "${ARGV${i}}")
    else()
      list(APPEND globs ${arg})
    endif()
    vera_incr(i)
  endwhile()

  if(recurse)
    file(GLOB_RECURSE srcs ${globs})
  else()
    file(GLOB srcs ${globs})
  endif()
  list(SORT srcs)

  if(NOT VERA++_EXECUTABLE AND TARGET vera)
    set(vera_program "$<TARGET_FILE:vera>")
  else()
    set(vera_program "${VERA++_EXECUTABLE}")
  endif()

  set(checkstylereports)
  set(reportNb 0)
  set(reportsrcs)
  list(GET srcs 0 first)
  get_filename_component(currentDir ${first} PATH)
  # add a fake src file in a fake dir to trigger the creation of the last
  # custom command
  list(APPEND srcs "#12345678900987654321#/0987654321#1234567890")
  # Create the directory where the reports will be saved
  SET(checkstyleDirectory "${CMAKE_CURRENT_BINARY_DIR}/checkstyle")
  FILE(MAKE_DIRECTORY ${checkstyleDirectory})
  foreach(s ${srcs})
    get_filename_component(d ${s} PATH)
    if(NOT "${d}" STREQUAL "${currentDir}")
      # this is a new dir - lets generate everything needed for the previous dir
      string(LENGTH "${CMAKE_SOURCE_DIR}" len)
      string(SUBSTRING "${currentDir}" 0 ${len} pre)
      if("${pre}" STREQUAL "${CMAKE_SOURCE_DIR}")
        string(SUBSTRING "${currentDir}" ${len} -1 currentDir)
        string(REGEX REPLACE "^/" "" currentDir "${currentDir}")
      endif()
      if("${currentDir}" STREQUAL "")
        set(currentDir ".")
      endif()
      set(checkstylereport ${checkstyleDirectory}/vera_checkstylereport_${reportNb}.xml)
      add_custom_command(
        OUTPUT ${checkstylereport}
        COMMAND ${vera_program}
          --root ${root}
          --profile ${profile}
          --show-rule
          --checkstyle-report ${checkstylereport}
          ${exclusions}
          ${parameters}
          ${parameterFiles}
          ${reportsrcs}
        DEPENDS ${reportsrcs}
        COMMENT "Checking style with vera++ in ${currentDir}"
      )
      list(APPEND checkstylereports ${checkstylereport})
      vera_incr(reportNb)
      # clear the list for the next dir
      set(reportsrcs)
      set(currentDir ${d})
    endif()
    list(APPEND reportsrcs ${s})
  endforeach()
  # Create the custom targets that will trigger the custom command created
  # previously
  add_custom_target(${target} DEPENDS ${checkstylereports})
endfunction()

macro(vera_incr var_name)
  math(EXPR ${var_name} "${${var_name}} + 1")
endmacro()
