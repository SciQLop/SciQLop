#include "Catalogue/CatalogueExplorerHelper.h"

#include <QBoxLayout>
#include <QToolButton>

const auto VALIDATION_BUTTON_ICON_SIZE = 12;

QWidget *CatalogueExplorerHelper::buildValidationWidget(QWidget *parent, std::function<void()> save,
                                                        std::function<void()> discard)
{
    auto widget = new QWidget{parent};

    auto layout = new QHBoxLayout{widget};
    layout->setContentsMargins(0, 0, 0, 0);
    layout->setSpacing(0);

    auto btnValid = new QToolButton{widget};
    btnValid->setIcon(QIcon{":/icones/save"});
    btnValid->setIconSize(QSize{VALIDATION_BUTTON_ICON_SIZE, VALIDATION_BUTTON_ICON_SIZE});
    btnValid->setAutoRaise(true);
    QObject::connect(btnValid, &QToolButton::clicked, save);
    layout->addWidget(btnValid);

    auto btnDiscard = new QToolButton{widget};
    btnDiscard->setIcon(QIcon{":/icones/discard"});
    btnDiscard->setIconSize(QSize{VALIDATION_BUTTON_ICON_SIZE, VALIDATION_BUTTON_ICON_SIZE});
    btnDiscard->setAutoRaise(true);
    QObject::connect(btnDiscard, &QToolButton::clicked, discard);
    layout->addWidget(btnDiscard);

    return widget;
}
