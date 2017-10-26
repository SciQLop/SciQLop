#include "SqpApplication.h"

#include <Data/IDataProvider.h>
#include <DataSource/DataSourceController.h>
#include <DragDropHelper.h>
#include <Network/NetworkController.h>
#include <QThread>
#include <Time/TimeController.h>
#include <Variable/Variable.h>
#include <Variable/VariableController.h>
#include <Visualization/VisualizationController.h>

Q_LOGGING_CATEGORY(LOG_SqpApplication, "SqpApplication")

class SqpApplication::SqpApplicationPrivate {
public:
    SqpApplicationPrivate()
            : m_DataSourceController{std::make_unique<DataSourceController>()},
              m_NetworkController{std::make_unique<NetworkController>()},
              m_TimeController{std::make_unique<TimeController>()},
              m_VariableController{std::make_unique<VariableController>()},
              m_VisualizationController{std::make_unique<VisualizationController>()},
              m_DragDropHelper{std::make_unique<DragDropHelper>()}
    {
        // /////////////////////////////// //
        // Connections between controllers //
        // /////////////////////////////// //

        // VariableController <-> DataSourceController
        connect(m_DataSourceController.get(),
                SIGNAL(variableCreationRequested(const QString &, const QVariantHash &,
                                                 std::shared_ptr<IDataProvider>)),
                m_VariableController.get(),
                SLOT(createVariable(const QString &, const QVariantHash &,
                                    std::shared_ptr<IDataProvider>)));

        // VariableController <-> VisualizationController
        connect(m_VariableController.get(),
                SIGNAL(variableAboutToBeDeleted(std::shared_ptr<Variable>)),
                m_VisualizationController.get(),
                SIGNAL(variableAboutToBeDeleted(std::shared_ptr<Variable>)), Qt::DirectConnection);

        connect(m_VariableController.get(),
                SIGNAL(rangeChanged(std::shared_ptr<Variable>, const SqpRange &)),
                m_VisualizationController.get(),
                SIGNAL(rangeChanged(std::shared_ptr<Variable>, const SqpRange &)));


        m_DataSourceController->moveToThread(&m_DataSourceControllerThread);
        m_DataSourceControllerThread.setObjectName("DataSourceControllerThread");
        m_NetworkController->moveToThread(&m_NetworkControllerThread);
        m_NetworkControllerThread.setObjectName("NetworkControllerThread");
        m_VariableController->moveToThread(&m_VariableControllerThread);
        m_VariableControllerThread.setObjectName("VariableControllerThread");
        m_VisualizationController->moveToThread(&m_VisualizationControllerThread);
        m_VisualizationControllerThread.setObjectName("VsualizationControllerThread");


        // Additionnal init
        m_VariableController->setTimeController(m_TimeController.get());
    }

    virtual ~SqpApplicationPrivate()
    {
        m_DataSourceControllerThread.quit();
        m_DataSourceControllerThread.wait();

        m_NetworkControllerThread.quit();
        m_NetworkControllerThread.wait();

        m_VariableControllerThread.quit();
        m_VariableControllerThread.wait();

        m_VisualizationControllerThread.quit();
        m_VisualizationControllerThread.wait();
    }

    std::unique_ptr<DataSourceController> m_DataSourceController;
    std::unique_ptr<VariableController> m_VariableController;
    std::unique_ptr<TimeController> m_TimeController;
    std::unique_ptr<NetworkController> m_NetworkController;
    std::unique_ptr<VisualizationController> m_VisualizationController;
    QThread m_DataSourceControllerThread;
    QThread m_NetworkControllerThread;
    QThread m_VariableControllerThread;
    QThread m_VisualizationControllerThread;

    std::unique_ptr<DragDropHelper> m_DragDropHelper;
};


SqpApplication::SqpApplication(int &argc, char **argv)
        : QApplication{argc, argv}, impl{spimpl::make_unique_impl<SqpApplicationPrivate>()}
{
    qCDebug(LOG_SqpApplication()) << tr("SqpApplication construction") << QThread::currentThread();

    connect(&impl->m_DataSourceControllerThread, &QThread::started,
            impl->m_DataSourceController.get(), &DataSourceController::initialize);
    connect(&impl->m_DataSourceControllerThread, &QThread::finished,
            impl->m_DataSourceController.get(), &DataSourceController::finalize);

    connect(&impl->m_NetworkControllerThread, &QThread::started, impl->m_NetworkController.get(),
            &NetworkController::initialize);
    connect(&impl->m_NetworkControllerThread, &QThread::finished, impl->m_NetworkController.get(),
            &NetworkController::finalize);

    connect(&impl->m_VariableControllerThread, &QThread::started, impl->m_VariableController.get(),
            &VariableController::initialize);
    connect(&impl->m_VariableControllerThread, &QThread::finished, impl->m_VariableController.get(),
            &VariableController::finalize);

    connect(&impl->m_VisualizationControllerThread, &QThread::started,
            impl->m_VisualizationController.get(), &VisualizationController::initialize);
    connect(&impl->m_VisualizationControllerThread, &QThread::finished,
            impl->m_VisualizationController.get(), &VisualizationController::finalize);

    impl->m_DataSourceControllerThread.start();
    impl->m_NetworkControllerThread.start();
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

NetworkController &SqpApplication::networkController() noexcept
{
    return *impl->m_NetworkController;
}

TimeController &SqpApplication::timeController() noexcept
{
    return *impl->m_TimeController;
}

VariableController &SqpApplication::variableController() noexcept
{
    return *impl->m_VariableController;
}

VisualizationController &SqpApplication::visualizationController() noexcept
{
    return *impl->m_VisualizationController;
}

DragDropHelper &SqpApplication::dragDropHelper() noexcept
{
    return *impl->m_DragDropHelper;
}
