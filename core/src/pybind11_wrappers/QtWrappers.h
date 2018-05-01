#pragma once
#include <QString>
#include <QUuid>
#include <QDate>
#include <QTime>
#include <string>
#include <sstream>

std::ostream &operator <<(std::ostream& os, const QString& qstr)
{
    os << qstr.toStdString();
    return os;
}

std::ostream &operator <<(std::ostream& os, const QUuid& uuid)
{
    os << "QUuid:" << uuid.toString() << std::endl;
    return os;
}
