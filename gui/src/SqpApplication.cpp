#include "SqpApplication.h"

#include <Actions/ActionsGuiController.h>
#include <Catalogue/CatalogueController.h>
#include <Data/IDataProvider.h>
#include <DataSource/DataSourceController.h>
#include <DragAndDrop/DragDropGuiController.h>
#include <Network/NetworkController.h>
#include <QThread>
#include <Time/TimeController.h>
#include <Variable/VariableController2.h>
#include <Variable/VariableModel2.h>
#include <Visualization/VisualizationController.h>

Q_LOGGING_CATEGORY(LOG_SqpApplication, "SqpApplication")

class SqpApplication::SqpApplicationPrivate
{
public:
    SqpApplicationPrivate()
            : m_VariableController { std::make_shared<VariableController2>() }
            , m_PlotInterractionMode(SqpApplication::PlotsInteractionMode::None)
            , m_PlotCursorMode(SqpApplication::PlotsCursorMode::NoCursor)
    {
        // /////////////////////////////// //
        // Connections between controllers //
        // /////////////////////////////// //

        // VariableController <-> DataSourceController
        connect(&m_DataSourceController, &DataSourceController::createVariable,
            [](const QString& variableName, const QVariantHash& variableMetadata,
                std::shared_ptr<IDataProvider> variableProvider) {
                sqpApp->variableController().createVariable(variableName, variableMetadata,
                    variableProvider, sqpApp->timeController().dateTime());
            });

        // VariableController <-> VisualizationController
        //        connect(m_VariableController.get(),
        //                SIGNAL(variableAboutToBeDeleted(std::shared_ptr<Variable>)),
        //                m_VisualizationController.get(),
        //                SIGNAL(variableAboutToBeDeleted(std::shared_ptr<Variable>)),
        //                Qt::DirectConnection);

        //        connect(m_VariableController.get(),
        //                SIGNAL(rangeChanged(std::shared_ptr<Variable>, const DateTimeRange &)),
        //                m_VisualizationController.get(),
        //                SIGNAL(rangeChanged(std::shared_ptr<Variable>, const DateTimeRange &)));


        m_DataSourceController.moveToThread(&m_DataSourceControllerThread);
        m_DataSourceControllerThread.setObjectName("DataSourceControllerThread");
        m_NetworkController.moveToThread(&m_NetworkControllerThread);
        m_NetworkControllerThread.setObjectName("NetworkControllerThread");
        m_VisualizationController.moveToThread(&m_VisualizationControllerThread);
        m_VisualizationControllerThread.setObjectName("VsualizationControllerThread");

        // Additionnal init
        // m_VariableController->setTimeController(m_TimeController.get());
    }

    virtual ~SqpApplicationPrivate()
    {
        m_DataSourceControllerThread.quit();
        m_DataSourceControllerThread.wait();

        m_NetworkControllerThread.quit();
        m_NetworkControllerThread.wait();

        m_VisualizationControllerThread.quit();
        m_VisualizationControllerThread.wait();
    }

    DataSourceController m_DataSourceController;
    std::shared_ptr<VariableController2> m_VariableController;
    TimeController m_TimeController;
    NetworkController m_NetworkController;
    VisualizationController m_VisualizationController;
    CatalogueController m_CatalogueController;

    QThread m_DataSourceControllerThread;
    QThread m_NetworkControllerThread;
    QThread m_VisualizationControllerThread;

    DragDropGuiController m_DragDropGuiController;
    ActionsGuiController m_ActionsGuiController;

    SqpApplication::PlotsInteractionMode m_PlotInterractionMode;
    SqpApplication::PlotsCursorMode m_PlotCursorMode;
};


SqpApplication::SqpApplication(int& argc, char** argv)
        : QApplication { argc, argv }, impl { spimpl::make_unique_impl<SqpApplicationPrivate>() }
{
    this->setStyle(new MyProxyStyle(this->style()));
    qCDebug(LOG_SqpApplication()) << tr("SqpApplication construction") << QThread::currentThread();

    QGuiApplication::setAttribute(Qt::AA_EnableHighDpiScaling);

    connect(&impl->m_DataSourceControllerThread, &QThread::started, &impl->m_DataSourceController,
        &DataSourceController::initialize);
    connect(&impl->m_DataSourceControllerThread, &QThread::finished, &impl->m_DataSourceController,
        &DataSourceController::finalize);

    connect(&impl->m_NetworkControllerThread, &QThread::started, &impl->m_NetworkController,
        &NetworkController::initialize);
    connect(&impl->m_NetworkControllerThread, &QThread::finished, &impl->m_NetworkController,
        &NetworkController::finalize);

    connect(&impl->m_VisualizationControllerThread, &QThread::started,
        &impl->m_VisualizationController, &VisualizationController::initialize);
    connect(&impl->m_VisualizationControllerThread, &QThread::finished,
        &impl->m_VisualizationController, &VisualizationController::finalize);

    impl->m_DataSourceControllerThread.start();
    impl->m_NetworkControllerThread.start();
    impl->m_VisualizationControllerThread.start();
    // impl->m_CatalogueController.initialize();
}

SqpApplication::~SqpApplication() {}

void SqpApplication::initialize() {}

DataSourceController& SqpApplication::dataSourceController() noexcept
{
    return impl->m_DataSourceController;
}

NetworkController& SqpApplication::networkController() noexcept
{
    return impl->m_NetworkController;
}

TimeController& SqpApplication::timeController() noexcept
{
    return impl->m_TimeController;
}

VariableController2& SqpApplication::variableController() noexcept
{
    return *impl->m_VariableController;
}

std::shared_ptr<VariableController2> SqpApplication::variableControllerOwner() noexcept
{
    return impl->m_VariableController;
}

// VariableModel2 &SqpApplication::variableModel() noexcept
//{
//    return impl->m_VariableModel;
//}

VisualizationController& SqpApplication::visualizationController() noexcept
{
    return impl->m_VisualizationController;
}

CatalogueController& SqpApplication::catalogueController() noexcept
{
    return impl->m_CatalogueController;
}

DragDropGuiController& SqpApplication::dragDropGuiController() noexcept
{
    return impl->m_DragDropGuiController;
}

ActionsGuiController& SqpApplication::actionsGuiController() noexcept
{
    return impl->m_ActionsGuiController;
}

SqpApplication::PlotsInteractionMode SqpApplication::plotsInteractionMode() const
{
    return impl->m_PlotInterractionMode;
}

void SqpApplication::setPlotsInteractionMode(SqpApplication::PlotsInteractionMode mode)
{
    impl->m_PlotInterractionMode = mode;
}

SqpApplication::PlotsCursorMode SqpApplication::plotsCursorMode() const
{
    return impl->m_PlotCursorMode;
}

void SqpApplication::setPlotsCursorMode(SqpApplication::PlotsCursorMode mode)
{
    impl->m_PlotCursorMode = mode;
}
