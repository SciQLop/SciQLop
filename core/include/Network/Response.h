#ifndef RESPONSE_H
#define RESPONSE_H

#include <QByteArray>
#include <QString>

/**
 * @brief The Response class holds a Network request response
 *
 */
class Response
{
    int _status_code;
    QByteArray _data;
public:
    Response(){}
    Response(QByteArray data, int status_code)
        :_status_code(status_code),_data(data)
    {

    }
    int status_code(){return _status_code;}
    QByteArray& data(){return _data;}
};
#endif // RESPONSE_H
