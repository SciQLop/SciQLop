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

class Downloader::p_Downloader
{
    using login_pair=QPair<QString,QString>;
    QNetworkAccessManager manager;
    QHash<QString,login_pair> auth;

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
        QNetworkReply *reply = manager.get(request);
        while (!reply->isFinished())
            QCoreApplication::processEvents();
        QVariant status_code = reply->attribute(QNetworkRequest::HttpStatusCodeAttribute);
        return Response(reply->readAll(), status_code.toInt());
    }
};

Response Downloader::get(const QString &url)
{
    return  Downloader::instance().impl->get(url);
}

Response Downloader::get(const QString &url, const QString &user, const QString &passwd)
{
    return  Downloader::instance().impl->get(url, user, passwd);
}

Downloader::Downloader()
    :impl(spimpl::make_unique_impl<p_Downloader>())
{
}

