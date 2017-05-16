#
# compiler_msvc.cmake : specific configuration for MSVC compilers
#

ADD_DEFINITIONS( /D _USE_MATH_DEFINES)
ADD_DEFINITIONS( /D _VARIADIC_MAX=10 )
ADD_DEFINITIONS( /D _CRT_SECURE_NO_WARNINGS)
