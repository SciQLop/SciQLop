#include "Catalogue/CatalogueExplorerHelper.h"

#include <QBoxLayout>
#include <QToolButton>


QWidget *CatalogueExplorerHelper::buildValidationWidget(QWidget *parent, std::function<void()> save,
                                                        std::function<void()> discard)
{
    auto widget = new QWidget{parent};

    auto layout = new QHBoxLayout{widget};

    auto btnValid = new QToolButton{widget};
    btnValid->setIcon(QIcon{":/icones/save"});
    btnValid->setAutoRaise(true);
    QObject::connect(btnValid, &QToolButton::clicked, save);
    layout->addWidget(btnValid);

    auto btnDiscard = new QToolButton{widget};
    btnDiscard->setIcon(QIcon{":/icones/discard"});
    btnDiscard->setAutoRaise(true);
    QObject::connect(btnDiscard, &QToolButton::clicked, discard);
    layout->addWidget(btnDiscard);

    layout->setContentsMargins(0, 0, 0, 0);
    layout->setSpacing(0);

    return widget;
}
