macro(declare_test testname testexe sources libraries)
    add_executable(${testexe} ${sources})
    target_link_libraries(${testexe} ${libraries})
    add_test(NAME ${testname} COMMAND ${testexe})
endmacro(declare_test)


macro(declare_manual_test testname testexe sources libraries)
    add_executable(${testexe} ${sources})
    target_link_libraries(${testexe} ${libraries})
endmacro(declare_manual_test)
