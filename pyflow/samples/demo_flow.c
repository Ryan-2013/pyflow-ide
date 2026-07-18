#include <stdio.h>

typedef struct {
    int value;
} Record;

int load_records(Record *records, int capacity) {
    if (capacity < 3) {
        return 0;
    }
    records[0].value = 3;
    records[1].value = -1;
    records[2].value = 7;
    return 3;
}

int validate_record(Record record) {
    return record.value >= 0;
}

Record normalize_record(Record record, int multiplier) {
    record.value *= multiplier;
    return record;
}

int process_records(Record *records, int count, int multiplier) {
    int clean_count = 0;
    for (int index = 0; index < count; index++) {
        if (validate_record(records[index])) {
            records[clean_count] = normalize_record(records[index], multiplier);
            clean_count++;
        }
    }
    return clean_count;
}

int summarize_records(const Record *records, int count) {
    int total = 0;
    for (int index = 0; index < count; index++) {
        total += records[index].value;
    }
    return total;
}

void save_report(int total) {
    printf("processed total: %d\n", total);
}

int run_pipeline(void) {
    Record records[8];
    int count = load_records(records, 8);
    int clean_count = process_records(records, count, 2);
    int total = summarize_records(records, clean_count);
    save_report(total);
    return total;
}

int main(void) {
    return run_pipeline() > 0 ? 0 : 1;
}
