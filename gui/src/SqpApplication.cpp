#include "SqpApplication.h"

#include <Data/IDataProvider.h>
#include <DataSource/DataSourceController.h>
#include <QThread>
#include <Variable/Variable.h>
#include <Variable/VariableController.h>
#include <Visualization/VisualizationController.h>

Q_LOGGING_CATEGORY(LOG_SqpApplication, "SqpApplication")

class SqpApplication::SqpApplicationPrivate {
public:
    SqpApplicationPrivate()
            : m_DataSourceController{std::make_unique<DataSourceController>()},
              m_VariableController{std::make_unique<VariableController>()},
              m_VisualizationController{std::make_unique<VisualizationController>()}
    {
        // /////////////////////////////// //
        // Connections between controllers //
        // /////////////////////////////// //

        // VariableController <-> DataSourceController
        qRegisterMetaType<std::shared_ptr<IDataProvider> >();
        connect(m_DataSourceController.get(),
                SIGNAL(variableCreationRequested(const QString &, std::shared_ptr<IDataProvider>)),
                m_VariableController.get(),
                SLOT(createVariable(const QString &, std::shared_ptr<IDataProvider>)));

        // VariableController <-> VisualizationController
        qRegisterMetaType<std::shared_ptr<Variable> >();
        connect(m_VariableController.get(), SIGNAL(variableCreated(std::shared_ptr<Variable>)),
                m_VisualizationController.get(),
                SLOT(onVariableCreated(std::shared_ptr<Variable>)));

        m_DataSourceController->moveToThread(&m_DataSourceControllerThread);
        m_VariableController->moveToThread(&m_VariableControllerThread);
        m_VisualizationController->moveToThread(&m_VisualizationControllerThread);
    }

    virtual ~SqpApplicationPrivate()
    {
        qCInfo(LOG_SqpApplication()) << tr("SqpApplicationPrivate destruction");
        m_DataSourceControllerThread.quit();
        m_DataSourceControllerThread.wait();

        m_VariableControllerThread.quit();
        m_VariableControllerThread.wait();

        m_VisualizationControllerThread.quit();
        m_VisualizationControllerThread.wait();
    }

    std::unique_ptr<DataSourceController> m_DataSourceController;
    std::unique_ptr<VariableController> m_VariableController;
    std::unique_ptr<VisualizationController> m_VisualizationController;
    QThread m_DataSourceControllerThread;
    QThread m_VariableControllerThread;
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

    connect(&impl->m_VariableControllerThread, &QThread::started, impl->m_VariableController.get(),
            &VariableController::initialize);
    connect(&impl->m_VariableControllerThread, &QThread::finished, impl->m_VariableController.get(),
            &VariableController::finalize);

    connect(&impl->m_VisualizationControllerThread, &QThread::started,
            impl->m_VisualizationController.get(), &VisualizationController::initialize);
    connect(&impl->m_VisualizationControllerThread, &QThread::finished,
            impl->m_VisualizationController.get(), &VisualizationController::finalize);

    impl->m_DataSourceControllerThread.start();
    impl->m_VariableControllerThread.start();
    impl->m_VisualizationControllerThread.start();
}

SqpApplication::~SqpApplication()
{
}

void SqpApplication::initialize()
{
}

DataSourceController &SqpApplication::dataSourceController() noexcept
{
    return *impl->m_DataSourceController;
}

VariableController &SqpApplication::variableController() noexcept
{
    return *impl->m_VariableController;
}

VisualizationController &SqpApplication::visualizationController() noexcept
{
    return *impl->m_VisualizationController;
}
