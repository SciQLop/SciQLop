#ifndef GUITESTUTILS_H
#define GUITESTUTILS_H

#include <types/detectors.hpp>
#include <QCoreApplication>
#include <QCursor>
#include <QDesktopWidget>
#include <QMouseEvent>
#include <QPoint>
#include <QtTest>

#include <SqpApplication.h>
#include <Variable/VariableController2.h>
#include <qcustomplot.h>

template <typename T>
QPoint center(T* widget)
{
    return QPoint { widget->width() / 2, widget->height() / 2 };
}

HAS_METHOD(has_viewport, viewport)

template <typename T>
static inline constexpr bool is_QWidgetOrDerived = std::is_base_of<QWidget, T>::value;

template <typename T>
using viewport_type = decltype(std::declval<T>().viewport());

HAS_METHOD(has_topLevelItem, topLevelItem)

template <typename T>
void mouseMove(T* widget, QPoint pos, Qt::MouseButton mouseModifier)
{
    QCursor::setPos(widget->mapToGlobal(pos));
    QMouseEvent event(QEvent::MouseMove, pos, Qt::NoButton, mouseModifier, Qt::NoModifier);
    if constexpr (has_viewport_v<T>)
    {
        if constexpr (is_QWidgetOrDerived<viewport_type<T>>)
        {
            qApp->sendEvent(widget->viewport(), &event);
        }
        else
        {
            qApp->sendEvent(widget, &event);
        }
    }
    else
    {
        qApp->sendEvent(widget, &event);
    }
    qApp->processEvents();
}


template <typename T>
void setMouseTracking(T* widget)
{
    if constexpr (has_viewport_v<T>)
    {
        if constexpr (is_QWidgetOrDerived<viewport_type<T>>)
        {
            widget->viewport()->setMouseTracking(true);
        }
        else
        {
            widget->setMouseTracking(true);
        }
    }
    else
    {
        widget->setMouseTracking(true);
    }
}

template <typename T, typename T2>
auto getItem(T* widget, T2 itemIndex)
{
    if constexpr (has_topLevelItem_v<T>)
    {
        return widget->topLevelItem(itemIndex);
    }
    else
    {
        return widget->item(itemIndex);
    }
}

#define SELECT_ITEM(widget, itemIndex, item)                                                       \
    auto item = getItem(widget, itemIndex);                                                        \
    {                                                                                              \
        auto itemCenterPos = widget->visualItemRect(item).center();                                \
        QTest::mouseClick(widget->viewport(), Qt::LeftButton, Qt::NoModifier, itemCenterPos);      \
        QVERIFY(widget->selectedItems().size() > 0);                                               \
        QVERIFY(widget->selectedItems().contains(item));                                           \
    }


#define GET_CHILD_WIDGET_FOR_GUI_TESTS(parent, child, childType, childName)                        \
    childType* child = parent.findChild<childType*>(childName);                                    \
    QVERIFY(child != Q_NULLPTR);                                                                   \
    setMouseTracking(child);

template <typename T1, typename T2, typename T3, typename T4 = void>
void dragnDropItem(T1* sourceWidget, T2* destWidget, T3* item, T4* destItem = Q_NULLPTR)
{
    auto itemCenterPos = sourceWidget->visualItemRect(item).center();
    if constexpr (has_viewport_v<T1>)
    {
        QTest::mousePress(sourceWidget->viewport(), Qt::LeftButton, Qt::NoModifier, itemCenterPos);
    }
    else
    {
        QTest::mousePress(sourceWidget, Qt::LeftButton, Qt::NoModifier, itemCenterPos);
    }
    mouseMove(sourceWidget, itemCenterPos, Qt::LeftButton);
    itemCenterPos += QPoint(0, -10);
    QTimer::singleShot(100, [destWidget, destItem]() {
        mouseMove(destWidget, destWidget->rect().center(), Qt::LeftButton);
        mouseMove(destWidget, destWidget->rect().center() + QPoint(0, -10), Qt::LeftButton);
        if constexpr (!std::is_same_v<void, T4>)
        {
            auto destItemCenterPos = destWidget->visualItemRect(destItem).center();
            QTest::mouseRelease(destWidget, Qt::LeftButton, Qt::NoModifier, destItemCenterPos);
        }
        else if constexpr (has_viewport_v<T2>)
        {
            QTest::mouseRelease(destWidget->viewport(), Qt::LeftButton);
        }
        else
        {
            QTest::mouseRelease(destWidget, Qt::LeftButton);
        }
        QTest::mouseRelease(destWidget->viewport(), Qt::LeftButton);
    });
    mouseMove(sourceWidget, itemCenterPos, Qt::LeftButton);
}

template <typename T>
void scroll_graph(T* w, int dx)
{
    auto cent = center(w);
    QTest::mousePress(w, Qt::LeftButton, Qt::NoModifier, cent, 1);
    mouseMove(w, { cent.x() + dx, cent.y() }, Qt::LeftButton);
    QTest::mouseRelease(w, Qt::LeftButton);
}

ALIAS_TEMPLATE_FUNCTION(isReady, static_cast<SqpApplication*>(qApp)->variableController().isReady)

void waitForVar(std::shared_ptr<Variable2> var)
{
    while (!isReady(var))
        QCoreApplication::processEvents();
}

template <typename T>
bool prepare_gui_test(T* w)
{
    w->setGeometry(QRect(
        QPoint(QApplication::desktop()->geometry().center() - QPoint(250, 250)), QSize(500, 500)));
    w->show();
    qApp->setActiveWindow(w);
    return QTest::qWaitForWindowActive(w);
}

#define GET_CHILD_WIDGET_FOR_GUI_TESTS(parent, child, childType, childName)                        \
    childType* child = parent.findChild<childType*>(childName);                                    \
    QVERIFY(child != Q_NULLPTR);                                                                   \
    setMouseTracking(child);

#endif
