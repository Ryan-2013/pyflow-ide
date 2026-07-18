package main

import "fmt"

type Record struct {
	Value int
}

type Pipeline struct {
	Multiplier int
}

func loadRecords() []Record {
	return []Record{{Value: 3}, {Value: -1}, {Value: 7}}
}

func validateRecord(record Record) bool {
	return record.Value >= 0
}

func normalizeRecord(record Record, multiplier int) Record {
	return Record{Value: record.Value * multiplier}
}

func summarizeRecords(records []Record) int {
	total := 0
	for _, record := range records {
		total += record.Value
	}
	return total
}

func saveReport(total int) {
	fmt.Printf("processed total: %d\n", total)
}

func (pipeline Pipeline) process(records []Record) []Record {
	clean := make([]Record, 0, len(records))
	for _, record := range records {
		if validateRecord(record) {
			clean = append(clean, normalizeRecord(record, pipeline.Multiplier))
		}
	}
	return clean
}

func (pipeline Pipeline) run() {
	raw := loadRecords()
	clean := pipeline.process(raw)
	total := summarizeRecords(clean)
	saveReport(total)
}

func say(){
	fmt.Printf("hi")
}

func main() {
	pipeline := Pipeline{Multiplier: 2}
	pipeline.run()
	go say()
	go say()
}
