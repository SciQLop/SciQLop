#include "Visualization/SqpColorScale.h"

namespace {

const auto DEFAULT_GRADIENT_PRESET = QCPColorGradient::gpJet;
const auto DEFAULT_RANGE = QCPRange{1.0e3, 1.7e7};

} // namespace

SqpColorScale::SqpColorScale(QCustomPlot &plot)
        : m_Scale{new QCPColorScale{&plot}},
          m_AutomaticThreshold{false},
          m_GradientPreset{DEFAULT_GRADIENT_PRESET}
{
    m_Scale->setGradient(m_GradientPreset);
    m_Scale->setDataRange(DEFAULT_RANGE);
}
