#ifndef DOWNLOADER_H
#define DOWNLOADER_H

#include "CoreGlobal.h"
#include "Response.h"

#include <Common/MetaTypes.h>
#include <Common/spimpl.h>
#include <functional>

#include <QString>
#include <QByteArray>
#include <QUuid>

/**
 * @brief The Downloader handles all data donwloads in SciQLOP.
 *
 * Simple synchronous GET example:
 * @code{.cpp}
 * auto response = Downloader::get("http://example.com")
 * std::cout << "Status code: " << response.status_code() << std::endl << "Data: " << response.data().toStdString() << std::endl;
 * @endcode
 *
 * @note
 * This is a quick and KISS implementation using QNetworkAccessManager isolating from Qt stuff (Signal/slots).
 * This could be impemented with a different backend in the future.
 *
 * @sa Response
 */
class SCIQLOP_CORE_EXPORT Downloader{
public:
    /**
     * @brief does a synchronous GET request on the given url
     * @param url
     * @param user
     * @param passwd
     * @return Response object containing request data and http status code
     * @sa Downloader::getAsync
     */
    static Response get(const QString& url, const QString& user="", const QString& passwd="");
    /**
     * @brief does an asynchronous GET request on the given url
     * @param url
     * @param callback
     * @param user
     * @param passwd
     * @return QUuid an unique identifier associated to this request
     * @sa Downloader::get, Downloader::downloadFinished
     */
    static QUuid getAsync(const QString& url, std::function<void (QUuid, Response)> callback, const QString& user="", const QString& passwd="");
    /**
     * @brief downloadFinished
     * @param uuid
     * @return true if the request associated to this uuid is complete
     */
    static bool downloadFinished(QUuid uuid);

    static Downloader& instance()
    {
        static Downloader inst;
        return  inst;
    }

private:
    class p_Downloader;

    explicit Downloader();

    spimpl::unique_impl_ptr<Downloader::p_Downloader> impl;
};

#endif // DOWNLOADER_H
