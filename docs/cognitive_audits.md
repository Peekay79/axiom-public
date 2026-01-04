# Cognitive Audits Documentation

This document describes Axiom's cognitive audit systems that provide self-reflective monitoring and quality assurance for the AI's internal reasoning processes.

## Overview

Cognitive audits are automated systems that periodically examine Axiom's internal state, beliefs, and reasoning processes to ensure consistency, quality, and coherence. These audits help maintain the integrity of the AI's cognitive architecture over time.

## Audit Types

### Reflexive Contradiction Auditor

The Reflexive Contradiction Auditor (`/workspace/audits/reflexive_contradiction_auditor.py`) provides ongoing self-coherence monitoring by detecting latent contradictions between stored beliefs.

#### Purpose

Create a self-reflective system that can detect **latent contradictions** between stored beliefs over time—not just on new belief ingestion. This enables ongoing self-coherence and belief system maintenance.

#### Features

- **Belief Loading**: Retrieves all stored beliefs or samples a subset for performance
- **Semantic Conflict Detection**: Uses NLI (Natural Language Inference) conflict checker to compare belief pairs
- **Intelligent Sampling**: Prevents combinatorial explosion with configurable sampling strategies
- **Detailed Logging**: Records conflicts with rich metadata in the journal system
- **CLI Interface**: Provides command-line access for manual audits
- **Graceful Fallbacks**: Works even when some system components are unavailable

#### Configuration

**Default Settings:**
- Conflict Threshold: `0.8` (minimum confidence to consider a conflict)
- Sample Size: `100` beliefs
- Maximum Pairs: `10,000` (prevents combinatorial explosion)

**Thresholds:**
- `>= 0.95`: Immediate review required
- `>= 0.9`: Schedule detailed analysis  
- `>= 0.85`: Flag for human review
- `< 0.85`: Monitor for patterns

#### Usage

**Command Line Interface:**

```bash
# Basic audit with default settings
python3 audits/reflexive_contradiction_auditor.py

# Sample 100 beliefs with custom threshold
python3 audits/reflexive_contradiction_auditor.py --sample 100 --threshold 0.8

# Verbose logging with output file
python3 audits/reflexive_contradiction_auditor.py --verbose --output audit_results.json

# Help and options
python3 audits/reflexive_contradiction_auditor.py --help
```

**Programmatic Usage:**

```python
from audits.reflexive_contradiction_auditor import ReflexiveContradictionAuditor

# Create auditor with custom threshold
auditor = ReflexiveContradictionAuditor(conflict_threshold=0.85)

# Run audit with sampling
results = auditor.run_audit(sample_size=200)

if results["success"]:
    print(f"Found {results['stats']['conflicts_found']} conflicts")
    print(f"Execution time: {results['execution_time_seconds']:.2f}s")
```

#### Audit Process

1. **Load Beliefs**: Retrieves beliefs from cognitive state manager or memory system
2. **Sample (Optional)**: Randomly samples beliefs if dataset is large
3. **Generate Pairs**: Creates combinations of belief pairs for comparison
4. **Conflict Detection**: Uses NLI semantic analysis to detect contradictions
5. **Filter by Threshold**: Only reports conflicts above confidence threshold
6. **Journal Logging**: Creates structured journal entries with audit results
7. **Action Suggestions**: Proposes resolution actions based on conflict severity

#### Journal Integration

Detected conflicts are automatically logged to the journal system with the tag `reflexive_contradiction`. Each journal entry includes:

- **Audit Statistics**: Beliefs loaded, pairs checked, conflicts found
- **High-Priority Conflicts**: Detailed breakdown of conflicts >0.9 confidence
- **Conflict Metadata**: Belief IDs, text content, explanation, proposed actions
- **Full Data**: Complete conflict data stored in entry metadata

#### Output Format

Audit results include:

```json
{
  "success": true,
  "execution_time_seconds": 12.34,
  "stats": {
    "beliefs_loaded": 150,
    "pairs_checked": 11175,
    "conflicts_found": 3,
    "errors": 0
  },
  "conflicts": [
    {
      "belief1_id": "belief_123",
      "belief2_id": "belief_456", 
      "belief1_text": "The sky is blue during clear weather",
      "belief2_text": "The sky is never blue",
      "conflict_score": 0.89,
      "explanation": "Semantic contradiction detected",
      "detected_at": "2025-01-14T10:30:00Z",
      "proposed_action": "flag_for_human_review"
    }
  ],
  "log_success": true
}
```

#### Implementation Details

**Belief Sources:**
1. Primary: `CognitiveStateManager.get_beliefs()`
2. Fallback: `Memory.snapshot()` filtered for belief-type entries
3. Mock: Generated test beliefs for development/testing

**Conflict Detection:**
- Uses `nli_conflict_checker.nli_check()` for semantic analysis
- Fallback to string-based pattern matching if NLI unavailable
- Configurable confidence thresholds for different actions

**Performance Optimizations:**
- Random sampling to limit dataset size
- Combinatorial pair limit (10K max) to prevent explosion
- Progress logging for large datasets
- Error handling to continue processing despite individual failures

#### Future Extensions

The following enhancements are planned as TODO items in the codebase:

- **Importance Ranking**: Rank contradictions by belief importance/confidence
- **Belief Clustering**: Group beliefs into coherent subnetworks for targeted analysis
- **Resolution Triggers**: Automatically trigger journaling tasks to resolve conflicts
- **Temporal Analysis**: Track how contradictions evolve over time
- **Human Review Interface**: Web dashboard for reviewing and resolving conflicts

#### Error Handling

The auditor includes robust error handling:

- **Component Availability**: Graceful fallbacks when system components unavailable
- **Individual Failures**: Continues processing despite errors in individual belief pairs
- **Resource Limits**: Prevents memory/CPU exhaustion with sampling limits
- **Detailed Logging**: Comprehensive error logging for debugging

#### Integration Points

The auditor integrates with these Axiom components:

- **CognitiveStateManager**: Primary source for belief retrieval
- **Memory Manager**: Fallback belief source and journal storage
- **NLI Conflict Checker**: Semantic contradiction detection
- **Journal Engine**: Audit result logging and reflection
- **Belief Core**: Future integration for belief metadata

---

## Running Audits

Cognitive audits can be run:

1. **On-Demand**: Via CLI for immediate analysis
2. **Scheduled**: Through cron jobs for regular monitoring  
3. **Triggered**: By events like belief updates or contradictions
4. **Programmatic**: Integrated into other Axiom processes

## Best Practices

- **Regular Scheduling**: Run reflexive audits weekly or bi-weekly
- **Threshold Tuning**: Adjust confidence thresholds based on false positive rates
- **Sample Sizing**: Balance completeness vs. performance with appropriate sampling
- **Journal Review**: Regularly review audit journal entries for patterns
- **Action Follow-up**: Implement processes to act on high-priority conflicts

## Monitoring and Metrics

Key metrics to track:

- **Conflict Rate**: Number of conflicts per beliefs examined
- **False Positive Rate**: Manual review of flagged conflicts  
- **Resolution Time**: Time from detection to conflict resolution
- **Audit Performance**: Execution time and resource usage
- **Coverage**: Percentage of belief system examined over time