// Neo4j Strand Memory Schema
// Extends the existing memory schema by mirroring memory nodes and linking them via RELATED edges.

// Node uniqueness and useful indexes
CREATE CONSTRAINT memory_id_unique IF NOT EXISTS FOR (m:Memory) REQUIRE (m.id) IS UNIQUE;
CREATE INDEX memory_type_index IF NOT EXISTS FOR (m:Memory) ON (m.memory_type);
CREATE INDEX memory_speaker_index IF NOT EXISTS FOR (m:Memory) ON (m.speaker);
CREATE INDEX memory_created_at_index IF NOT EXISTS FOR (m:Memory) ON (m.created_at);

// Relationships are merged to avoid duplicates; we do not enforce relationship-level uniqueness here.