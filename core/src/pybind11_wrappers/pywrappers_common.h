#ifndef PYWRAPPERS_COMMON_H
#define PYWRAPPERS_COMMON_H
#include <QString>
#include <string>
#include <sstream>
#include <QUuid>
#include <pybind11/pybind11.h>


template <typename T>
std::string __repr__(const T& obj)
{
    std::stringstream sstr;
    sstr << obj;
    return sstr.str();
}

#endif //PYWRAPPERS_COMMON_H
