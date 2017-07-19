#include "CosinusProvider.h"

#include <Data/DataProviderParameters.h>
#include <Data/ScalarSeries.h>

#include <cmath>

#include <QDateTime>
#include <QFuture>
#include <QThread>
#include <QtConcurrent/QtConcurrent>

Q_LOGGING_CATEGORY(LOG_CosinusProvider, "CosinusProvider")

std::shared_ptr<IDataSeries> CosinusProvider::retrieveData(QUuid token, const SqpDateTime &dateTime)
{
    // TODO: Add Mutex
    auto dataIndex = 0;

    // Gets the timerange from the parameters
    double freq = 100.0;
    double start = dateTime.m_TStart * freq; // 100 htz
    double end = dateTime.m_TEnd * freq;     // 100 htz

    // We assure that timerange is valid
    if (end < start) {
        std::swap(start, end);
    }

    // Generates scalar series containing cosinus values (one value per second)
    auto scalarSeries
        = std::make_shared<ScalarSeries>(end - start, Unit{QStringLiteral("t"), true}, Unit{});


    int progress = 0;
    auto progressEnd = end - start;
    for (auto time = start; time < end; ++time, ++dataIndex) {
        auto it = m_VariableToEnableProvider.find(token);
        if (it != m_VariableToEnableProvider.end() && it.value()) {
            const auto timeOnFreq = time / freq;
            scalarSeries->setData(dataIndex, timeOnFreq, std::cos(timeOnFreq));

            // progression
            int currentProgress = (time - start) * 100.0 / progressEnd;
            if (currentProgress != progress) {
                progress = currentProgress;

                emit dataProvidedProgress(token, progress);
            }
        }
        else {
            if (!it.value()) {
                qCDebug(LOG_CosinusProvider())
                    << "CosinusProvider::retrieveData: ARRET De l'acquisition detecté"
                    << end - time;
            }
        }
    }
    emit dataProvidedProgress(token, 0.0);


    return scalarSeries;
}

void CosinusProvider::requestDataLoading(QUuid token, const DataProviderParameters &parameters)
{
    // TODO: Add Mutex
    m_VariableToEnableProvider[token] = true;
    qCDebug(LOG_CosinusProvider()) << "CosinusProvider::requestDataLoading"
                                   << QThread::currentThread()->objectName();
    // NOTE: Try to use multithread if possible
    const auto times = parameters.m_Times;

    for (const auto &dateTime : qAsConst(times)) {
        if (m_VariableToEnableProvider[token]) {
            auto scalarSeries = this->retrieveData(token, dateTime);
            emit dataProvided(token, scalarSeries, dateTime);
        }
    }
}

void CosinusProvider::requestDataAborting(QUuid identifier)
{
    // TODO: Add Mutex
    qCDebug(LOG_CosinusProvider()) << "CosinusProvider::requestDataAborting" << identifier
                                  << QThread::currentThread()->objectName();
    auto it = m_VariableToEnableProvider.find(identifier);
    if (it != m_VariableToEnableProvider.end()) {
        it.value() = false;
    }
    else {
        qCWarning(LOG_CosinusProvider())
            << tr("Aborting progression of inexistant identifier detected !!!");
    }
}
