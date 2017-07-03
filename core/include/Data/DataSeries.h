#ifndef SCIQLOP_DATASERIES_H
#define SCIQLOP_DATASERIES_H

#include <Data/ArrayData.h>
#include <Data/IDataSeries.h>

#include <QLoggingCategory>

#include <memory>


Q_DECLARE_LOGGING_CATEGORY(LOG_DataSeries)
Q_LOGGING_CATEGORY(LOG_DataSeries, "DataSeries")


/**
 * @brief The DataSeries class is the base (abstract) implementation of IDataSeries.
 *
 * It proposes to set a dimension for the values ​​data
 *
 * @tparam Dim The dimension of the values data
 *
 */
template <int Dim>
class DataSeries : public IDataSeries {
public:
    /// @sa IDataSeries::xAxisData()
    std::shared_ptr<ArrayData<1> > xAxisData() override { return m_XAxisData; }
    const std::shared_ptr<ArrayData<1> > xAxisData() const { return m_XAxisData; }

    /// @sa IDataSeries::xAxisUnit()
    Unit xAxisUnit() const override { return m_XAxisUnit; }

    /// @return the values dataset
    std::shared_ptr<ArrayData<Dim> > valuesData() { return m_ValuesData; }
    const std::shared_ptr<ArrayData<Dim> > valuesData() const { return m_ValuesData; }

    /// @sa IDataSeries::valuesUnit()
    Unit valuesUnit() const override { return m_ValuesUnit; }

    /// @sa IDataSeries::merge()
    void merge(IDataSeries *dataSeries) override
    {
        if (auto dimDataSeries = dynamic_cast<DataSeries<Dim> *>(dataSeries)) {
            m_XAxisData->merge(*dimDataSeries->xAxisData());
            m_ValuesData->merge(*dimDataSeries->valuesData());
        }
        else {
            qCWarning(LOG_DataSeries())
                << QObject::tr("Dection of a type of IDataSeries we cannot merge with !");
        }
    }

protected:
    /// Protected ctor (DataSeries is abstract)
    explicit DataSeries(std::shared_ptr<ArrayData<1> > xAxisData, const Unit &xAxisUnit,
                        std::shared_ptr<ArrayData<Dim> > valuesData, const Unit &valuesUnit)
            : m_XAxisData{xAxisData},
              m_XAxisUnit{xAxisUnit},
              m_ValuesData{valuesData},
              m_ValuesUnit{valuesUnit}
    {
    }

    /// Copy ctor
    explicit DataSeries(const DataSeries<Dim> &other)
            : m_XAxisData{std::make_shared<ArrayData<1> >(*other.m_XAxisData)},
              m_XAxisUnit{other.m_XAxisUnit},
              m_ValuesData{std::make_shared<ArrayData<Dim> >(*other.m_ValuesData)},
              m_ValuesUnit{other.m_ValuesUnit}
    {
    }

    /// Assignment operator
    template <int D>
    DataSeries &operator=(DataSeries<D> other)
    {
        std::swap(m_XAxisData, other.m_XAxisData);
        std::swap(m_XAxisUnit, other.m_XAxisUnit);
        std::swap(m_ValuesData, other.m_ValuesData);
        std::swap(m_ValuesUnit, other.m_ValuesUnit);

        return *this;
    }

private:
    std::shared_ptr<ArrayData<1> > m_XAxisData;
    Unit m_XAxisUnit;
    std::shared_ptr<ArrayData<Dim> > m_ValuesData;
    Unit m_ValuesUnit;
};

#endif // SCIQLOP_DATASERIES_H
