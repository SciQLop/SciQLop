#include "CosinusProvider.h"

#include <Data/DataProviderParameters.h>
#include <Data/ScalarSeries.h>

#include <cmath>

#include <QFuture>
#include <QThread>
#include <QtConcurrent/QtConcurrent>

Q_LOGGING_CATEGORY(LOG_CosinusProvider, "CosinusProvider")

std::shared_ptr<IDataProvider> CosinusProvider::clone() const
{
    // No copy is made in clone
    return std::make_shared<CosinusProvider>();
}

std::shared_ptr<IDataSeries> CosinusProvider::retrieveData(QUuid acqIdentifier,
                                                           const SqpRange &dataRangeRequested)
{
    // TODO: Add Mutex
    auto dataIndex = 0;

    // Gets the timerange from the parameters
    double freq = 100.0;
    double start = std::ceil(dataRangeRequested.m_TStart * freq); // 100 htz
    double end = std::floor(dataRangeRequested.m_TEnd * freq);    // 100 htz

    // We assure that timerange is valid
    if (end < start) {
        std::swap(start, end);
    }

    // Generates scalar series containing cosinus values (one value per second, end value is
    // included)
    auto dataCount = end - start + 1;

    auto xAxisData = std::vector<double>{};
    xAxisData.resize(dataCount);

    auto valuesData = std::vector<double>{};
    valuesData.resize(dataCount);

    int progress = 0;
    auto progressEnd = dataCount;
    for (auto time = start; time <= end; ++time, ++dataIndex) {
        auto it = m_VariableToEnableProvider.find(acqIdentifier);
        if (it != m_VariableToEnableProvider.end() && it.value()) {
            const auto timeOnFreq = time / freq;

            xAxisData[dataIndex] = timeOnFreq;
            valuesData[dataIndex] = std::cos(timeOnFreq);

            // progression
            int currentProgress = (time - start) * 100.0 / progressEnd;
            if (currentProgress != progress) {
                progress = currentProgress;

                emit dataProvidedProgress(acqIdentifier, progress);
                qCInfo(LOG_CosinusProvider()) << "TORM: CosinusProvider::retrieveData"
                                              << QThread::currentThread()->objectName() << progress;
                // NOTE: Try to use multithread if possible
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
    if (progress != 100) {
        // We can close progression beacause all data has been retrieved
        emit dataProvidedProgress(acqIdentifier, 100);
    }
    return std::make_shared<ScalarSeries>(std::move(xAxisData), std::move(valuesData),
                                          Unit{QStringLiteral("t"), true}, Unit{});
}

void CosinusProvider::requestDataLoading(QUuid acqIdentifier,
                                         const DataProviderParameters &parameters)
{
    // TODO: Add Mutex
    m_VariableToEnableProvider[acqIdentifier] = true;
    qCDebug(LOG_CosinusProvider()) << "TORM: CosinusProvider::requestDataLoading"
                                   << QThread::currentThread()->objectName();
    // NOTE: Try to use multithread if possible
    const auto times = parameters.m_Times;

    for (const auto &dateTime : qAsConst(times)) {
        if (m_VariableToEnableProvider[acqIdentifier]) {
            auto scalarSeries = this->retrieveData(acqIdentifier, dateTime);
            qCDebug(LOG_CosinusProvider()) << "TORM: CosinusProvider::dataProvided";
            emit dataProvided(acqIdentifier, scalarSeries, dateTime);
        }
    }
}

void CosinusProvider::requestDataAborting(QUuid acqIdentifier)
{
    // TODO: Add Mutex
    qCDebug(LOG_CosinusProvider()) << "CosinusProvider::requestDataAborting" << acqIdentifier
                                   << QThread::currentThread()->objectName();
    auto it = m_VariableToEnableProvider.find(acqIdentifier);
    if (it != m_VariableToEnableProvider.end()) {
        it.value() = false;
    }
    else {
        qCWarning(LOG_CosinusProvider())
            << tr("Aborting progression of inexistant identifier detected !!!");
    }
}
