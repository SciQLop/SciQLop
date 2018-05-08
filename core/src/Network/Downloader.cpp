#include <Network/Downloader.h>
#include <memory>

#include <QNetworkRequest>
#include <QNetworkReply>
#include <QNetworkAccessManager>
#include <QAuthenticator>
#include <QVariant>
#include <QHash>
#include <QPair>
#include <QCoreApplication>
#include <QReadWriteLock>

class Downloader::p_Downloader
{
    using login_pair=QPair<QString,QString>;
    QNetworkAccessManager manager;
    QHash<QString,login_pair> auth;
    QReadWriteLock pending_requests_lock;
    QHash<QUuid,QNetworkReply*> pending_requests;

    QNetworkRequest buildRequest(const QString& url, const QString &user="", const QString &passwd="")
    {
        QNetworkRequest request;
        request.setUrl(QUrl(url));
        request.setRawHeader("User-Agent", "SciQLop 1.0");
        if(user!="" and passwd!="")
        {
            //might grow quickly since we can have tons of URLs for the same host
            auth[url]=login_pair(user,passwd);
            QString login = "Basic "+user+":"+passwd;
            request.setRawHeader("Authorization",login.toLocal8Bit());
        }
        return request;
    }

public:
    explicit p_Downloader()
    {

        auto login_bambda = [this](QNetworkReply * reply, QAuthenticator * authenticator)
        {
            if(auth.contains(reply->url().toString()))
            {
                auto login = auth[reply->url().toString()];
                authenticator->setUser(login.first);
                authenticator->setPassword(login.second);
            }
        };

        QObject::connect(&manager, &QNetworkAccessManager::authenticationRequired, login_bambda);
    }

    Response get(const QString& url, const QString &user="", const QString &passwd="")
    {
        QNetworkRequest request = buildRequest(url, user, passwd);
        QNetworkReply *reply = manager.get(request);
        while (!reply->isFinished())
            QCoreApplication::processEvents();
        QVariant status_code = reply->attribute(QNetworkRequest::HttpStatusCodeAttribute);
        Response resp = Response(reply->readAll(), status_code.toInt());
        delete reply;
        if(user!="" and passwd!="")
            auth.remove(url);
        return resp;
    }

    QUuid getAsync(const QString &url, std::function<void (QUuid ,Response)> callback, const QString &user, const QString &passwd)
    {
        auto uuid = QUuid::createUuid();
        QNetworkRequest request = buildRequest(url, user, passwd);
        QNetworkReply *reply = manager.get(request);
        auto callback_wrapper = [url, uuid, callback, this](){
            QNetworkReply* reply;
            {
                QWriteLocker locker(&pending_requests_lock);
                reply = pending_requests.take(uuid);
            }
            QVariant status_code = reply->attribute(QNetworkRequest::HttpStatusCodeAttribute);
            Response resp = Response(reply->readAll(), status_code.toInt());
            auth.remove(url);
            delete reply;
            callback(uuid, resp);
        };
        QObject::connect(reply, &QNetworkReply::finished, callback_wrapper);
        {
            QWriteLocker locker(&pending_requests_lock);
            pending_requests[uuid] = reply;
        }
        return uuid;
    }
    bool downloadFinished(QUuid uuid)
    {
        QReadLocker locker(&pending_requests_lock);
        if(pending_requests.contains(uuid))
        {
            auto req = pending_requests[uuid];
            return req->isFinished();
        }
        return true;
    }
};

Response Downloader::get(const QString &url, const QString &user, const QString &passwd)
{
    return  Downloader::instance().impl->get(url, user, passwd);
}

QUuid Downloader::getAsync(const QString &url, std::function<void (QUuid ,Response)> callback, const QString &user, const QString &passwd)
{
    return  Downloader::instance().impl->getAsync(url, callback, user, passwd);
}

bool Downloader::downloadFinished(QUuid uuid)
{
    return Downloader::instance().impl->downloadFinished(uuid);
}

Downloader::Downloader()
    :impl(spimpl::make_unique_impl<p_Downloader>())
{
}

