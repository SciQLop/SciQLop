#ifndef SCIQLOP_AMDARESULTPARSERHELPER_H
#define SCIQLOP_AMDARESULTPARSERHELPER_H

#include "AmdaResultParserDefs.h"

#include <QtCore/QLoggingCategory>
#include <QtCore/QString>

#include <memory>

class IDataSeries;

Q_DECLARE_LOGGING_CATEGORY(LOG_AmdaResultParserHelper)

/**
 * Helper used to interpret the data of an AMDA result file and generate the corresponding data
 * series.
 *
 * It proposes methods allowing to read line by line an AMDA file and to extract the properties
 * (from the header) and the values corresponding to the data series
 *
 * @sa DataSeries
 */
struct IAmdaResultParserHelper {
    virtual ~IAmdaResultParserHelper() noexcept = default;

    /// Verifies that the extracted properties are well formed and possibly applies other treatments
    /// on them
    /// @return true if the properties are well formed, false otherwise
    virtual bool checkProperties() = 0;

    /// Creates the data series from the properties and values extracted from the AMDA file.
    /// @warning as the data are moved in the data series, the helper shouldn't be used after
    /// calling this method
    /// @return the data series created
    virtual std::shared_ptr<IDataSeries> createSeries() = 0;

    /// Reads a line from the AMDA file to extract a property that will be used to generate the data
    /// series
    /// @param line tahe line to interpret
    virtual void readPropertyLine(const QString &line) = 0;

    /// Reads a line from the AMDA file to extract a value that will be set in the data series
    /// @param line the line to interpret
    virtual void readResultLine(const QString &line) = 0;
};

/**
 * Implementation of @sa IAmdaResultParserHelper for scalars
 */
class ScalarParserHelper : public IAmdaResultParserHelper {
public:
    bool checkProperties() override;
    std::shared_ptr<IDataSeries> createSeries() override;
    void readPropertyLine(const QString &line) override;
    void readResultLine(const QString &line) override;

private:
    /// @return the reading order of the "value" columns for a result line of the AMDA file
    std::vector<int> valuesIndexes() const;

    Properties m_Properties{};
    std::vector<double> m_XAxisData{};
    std::vector<double> m_ValuesData{};
};

/**
 * Implementation of @sa IAmdaResultParserHelper for spectrograms
 */
class SpectrogramParserHelper : public IAmdaResultParserHelper {
public:
    bool checkProperties() override;
    std::shared_ptr<IDataSeries> createSeries() override;
    void readPropertyLine(const QString &line) override;
    void readResultLine(const QString &line) override;
};

/**
 * Implementation of @sa IAmdaResultParserHelper for vectors
 */
class VectorParserHelper : public IAmdaResultParserHelper {
public:
    bool checkProperties() override;
    std::shared_ptr<IDataSeries> createSeries() override;
    void readPropertyLine(const QString &line) override;
    void readResultLine(const QString &line) override;

private:
    /// @return the reading order of the "value" columns for a result line of the AMDA file
    std::vector<int> valuesIndexes() const;

    Properties m_Properties{};
    std::vector<double> m_XAxisData{};
    std::vector<double> m_ValuesData{};
};

#endif // SCIQLOP_AMDARESULTPARSERHELPER_H
