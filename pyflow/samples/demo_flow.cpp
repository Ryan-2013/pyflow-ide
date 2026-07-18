#include <iostream>
#include <vector>

struct Record {
    int value;
};

std::vector<Record> loadRecords() {
    return {{3}, {-1}, {7}};
}

bool validateRecord(const Record &record) {
    return record.value >= 0;
}

Record normalizeRecord(Record record, int multiplier) {
    record.value *= multiplier;
    return record;
}

std::vector<Record> processRecords(
    const std::vector<Record> &records,
    int multiplier
) {
    std::vector<Record> clean;
    for (const Record &record : records) {
        if (validateRecord(record)) {
            clean.push_back(normalizeRecord(record, multiplier));
        }
    }
    return clean;
}

int summarizeRecords(const std::vector<Record> &records) {
    int total = 0;
    for (const Record &record : records) {
        total += record.value;
    }
    return total;
}

void saveReport(int total) {
    std::cout << "processed total: " << total << '\n';
}

int runPipeline() {
    const std::vector<Record> raw = loadRecords();
    const std::vector<Record> clean = processRecords(raw, 2);
    const int total = summarizeRecords(clean);
    saveReport(total);
    return total;
}

int main() {
    return runPipeline() > 0 ? 0 : 1;
}
