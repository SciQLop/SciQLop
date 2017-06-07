#include "SqpApplication.h"

#include <DataSource/DataSourceController.h>
#include <QThread>
#include <Visualization/VisualizationController.h>

Q_LOGGING_CATEGORY(LOG_SqpApplication, "SqpApplication")

class SqpApplication::SqpApplicationPrivate {
public:
    SqpApplicationPrivate()
            : m_DataSourceController{std::make_unique<DataSourceController>()},
              m_VisualizationController{std::make_unique<VisualizationController>()}
    {
        m_DataSourceController->moveToThread(&m_DataSourceControllerThread);
        m_VisualizationController->moveToThread(&m_VisualizationControllerThread);
    }

    virtual ~SqpApplicationPrivate()
    {
        qCInfo(LOG_SqpApplication()) << tr("SqpApplicationPrivate destruction");
        m_DataSourceControllerThread.quit();
        m_DataSourceControllerThread.wait();

        m_VisualizationControllerThread.quit();
        m_VisualizationControllerThread.wait();
    }

    std::unique_ptr<DataSourceController> m_DataSourceController;
    std::unique_ptr<VisualizationController> m_VisualizationController;
    QThread m_DataSourceControllerThread;
    QThread m_VisualizationControllerThread;
};


SqpApplication::SqpApplication(int &argc, char **argv)
        : QApplication{argc, argv}, impl{spimpl::make_unique_impl<SqpApplicationPrivate>()}
{
    qCInfo(LOG_SqpApplication()) << tr("SqpApplication construction");

    connect(&impl->m_DataSourceControllerThread, &QThread::started,
            impl->m_DataSourceController.get(), &DataSourceController::initialize);
    connect(&impl->m_DataSourceControllerThread, &QThread::finished,
            impl->m_DataSourceController.get(), &DataSourceController::finalize);

    connect(&impl->m_VisualizationControllerThread, &QThread::started,
            impl->m_VisualizationController.get(), &VisualizationController::initialize);
    connect(&impl->m_VisualizationControllerThread, &QThread::finished,
            impl->m_VisualizationController.get(), &VisualizationController::finalize);


    impl->m_DataSourceControllerThread.start();
    impl->m_VisualizationControllerThread.start();
}

SqpApplication::~SqpApplication()
{
}

void SqpApplication::initialize()
{
}

DataSourceController &SqpApplication::dataSourceController() const noexcept
{
    return *impl->m_DataSourceController;
}

VisualizationController &SqpApplication::visualizationController() const noexcept
{
    return *impl->m_VisualizationController;
}
