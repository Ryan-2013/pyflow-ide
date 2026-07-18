#[derive(Clone, Copy)]
struct Record {
    value: i32,
}

struct Pipeline {
    multiplier: i32,
}

fn load_records() -> Vec<Record> {
    vec![Record { value: 3 }, Record { value: -1 }, Record { value: 7 }]
}

fn validate_record(record: &Record) -> bool {
    record.value >= 0
}

fn normalize_record(record: Record, multiplier: i32) -> Record {
    Record {
        value: record.value * multiplier,
    }
}

fn summarize_records(records: &[Record]) -> i32 {
    records.iter().map(|record| record.value).sum()
}

fn save_report(total: i32) {
    println!("processed total: {total}");
}

impl Pipeline {
    fn process(&self, records: Vec<Record>) -> Vec<Record> {
        records
            .into_iter()
            .filter(|record| validate_record(record))
            .map(|record| normalize_record(record, self.multiplier))
            .collect()
    }

    fn run(&self) {
        let raw = load_records();
        let clean = self.process(raw);
        let total = summarize_records(&clean);
        save_report(total);
    }
}

fn main() {
    let pipeline = Pipeline { multiplier: 2 };
    pipeline.run();
}
