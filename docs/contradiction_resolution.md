# Contradiction Resolution Engine

**Production-grade automated resolution system for belief contradictions in Axiom**

## Overview

The Contradiction Resolution Engine automatically resolves conflicts between stored beliefs using heuristics, semantic reasoning, and Theory of Mind simulations. It processes contradictions flagged by the Reflexive Contradiction Auditor and applies various strategies to maintain belief system coherence.

## Features

- **Multi-source conflict loading**: Journal engine integration with audit file fallback
- **Intelligent prioritization**: Ranks conflicts by confidence, importance, age, and frequency
- **Multiple resolution strategies**: Deletion, reframing, simulated dialogue, and human deferral
- **Full audit trail**: Complete logging and reversibility support
- **Production safeguards**: Ethics constraints and human review requirements
- **Integration**: Seamless integration with belief registry, memory manager, and Theory of Mind

## Installation & Setup

```bash
# The engine is part of the core Axiom system
cd /workspace
python3 -m pip install -r requirements.txt

# Verify dependencies
python3 -c "from contradiction_resolution_engine import ContradictionResolver; print('✅ Ready')"
```

## Quick Start

### Basic Usage

```python
from contradiction_resolution_engine import ContradictionResolver

# Initialize resolver
resolver = ContradictionResolver()

# Run full resolution pipeline
report = resolver.run_resolution_pipeline(sample_size=50)

print(f"Processed: {report['total_conflicts_processed']} conflicts")
print(f"Deleted: {report['resolution_breakdown']['deleted']} beliefs")
print(f"Reframed: {report['resolution_breakdown']['reframed']} beliefs")
```

### CLI Usage

```bash
# Basic resolution with default settings
python3 contradiction_resolution_engine.py

# Process specific number of conflicts
python3 contradiction_resolution_engine.py --sample-size 25

# Load from specific source file
python3 contradiction_resolution_engine.py --source /path/to/conflicts.json

# Save results to file
python3 contradiction_resolution_engine.py --output results.json

# Enable verbose logging
python3 contradiction_resolution_engine.py --verbose
```

## API Reference

### ContradictionResolver

Main resolution engine class that orchestrates the contradiction resolution process.

#### Constructor

```python
ContradictionResolver(config: Optional[Dict[str, Any]] = None)
```

**Parameters:**
- `config`: Optional configuration dictionary for customizing behavior

**Example:**
```python
config = {
    "min_confidence_threshold": 0.2,
    "high_importance_threshold": 0.85,
    "enable_reframing": True
}
resolver = ContradictionResolver(config)
```

#### Core Methods

##### `load_conflicts(source: Optional[str] = None) -> List[BeliefPair]`

Load unresolved contradiction data from various sources.

**Parameters:**
- `source`: Optional path to specific conflict file

**Returns:**
- List of `BeliefPair` objects representing conflicts

**Data Sources (in priority order):**
1. Journal engine (`reflexive_contradiction` tagged entries)
2. Audit files (`/workspace/audits/reflexive_contradictions*.json`)
3. Log files (`/workspace/data/logs/reflexive_contradictions*.json`)

**Example:**
```python
# Auto-detect sources
conflicts = resolver.load_conflicts()

# Load from specific file
conflicts = resolver.load_conflicts("/path/to/conflicts.json")
```

##### `prioritize_conflicts(conflicts: List[BeliefPair]) -> List[BeliefPair]`

Rank conflicts by priority using multiple criteria.

**Prioritization Factors:**
- **Conflict confidence**: Higher confidence conflicts prioritized
- **Belief importance**: Combined importance of conflicting beliefs
- **Belief confidence**: Lower confidence beliefs prioritized for resolution
- **Age**: Older beliefs considered more suspect (when timestamp available)

**Example:**
```python
prioritized = resolver.prioritize_conflicts(conflicts)
# Returns conflicts sorted by priority score (highest first)
```

##### `resolve_conflict(pair: BeliefPair) -> ResolutionResult`

Resolve a single conflict using appropriate strategy.

**Resolution Strategies:**
1. **Low-confidence deletion**: Remove beliefs below confidence threshold
2. **Reframing**: Rewrite beliefs with similar semantic cores but different framing
3. **Simulated dialogue**: Use Theory of Mind to model agent explanations
4. **Human deferral**: Flag high-importance/confidence conflicts for review

**Example:**
```python
pair = conflicts[0]
result = resolver.resolve_conflict(pair)

print(f"Action: {result.action}")
print(f"Strategy: {result.strategy_used}")
print(f"Explanation: {result.explanation}")
```

##### `run_resolution_pipeline(sample_size: int = 100) -> Dict[str, Any]`

Execute the complete resolution pipeline.

**Pipeline Steps:**
1. Load conflicts from available sources
2. Prioritize conflicts by multiple criteria
3. Process top N conflicts (limited by `sample_size`)
4. Apply resolution strategies
5. Update belief registry and memory
6. Log outcomes and generate report

**Example:**
```python
# Process top 50 conflicts
report = resolver.run_resolution_pipeline(sample_size=50)

# Access detailed results
for result in report['results']:
    print(f"Conflict {result['conflict_id']}: {result['action']}")
```

### Data Models

#### BeliefPair

Represents a pair of conflicting beliefs.

```python
@dataclass
class BeliefPair:
    belief_a: Union[Dict[str, Any], Belief]
    belief_b: Union[Dict[str, Any], Belief]
    conflict_id: str
    conflict_data: Dict[str, Any]
    priority_score: float = 0.0
```

**Helper Methods:**
- `get_belief_a_id()` / `get_belief_b_id()`: Extract belief IDs
- `get_belief_a_text()` / `get_belief_b_text()`: Extract statement texts
- `get_belief_a_confidence()` / `get_belief_b_confidence()`: Extract confidence scores
- `get_belief_a_importance()` / `get_belief_b_importance()`: Extract importance scores

#### ResolutionResult

Result of resolving a belief conflict.

```python
@dataclass
class ResolutionResult:
    conflict_id: str
    action: str  # 'deleted', 'reframed', 'flagged', 'dialogue_resolved', 'deferred'
    updated_beliefs: Optional[List[Union[Dict[str, Any], Belief]]] = None
    deleted_beliefs: Optional[List[str]] = None
    explanation: str = ""
    confidence: float = 0.0
    strategy_used: str = ""
    human_review_required: bool = False
```

**Actions:**
- `deleted`: One or more beliefs removed
- `reframed`: Belief rewritten to resolve conflict
- `dialogue_resolved`: Resolved through ToM simulation
- `flagged`: Marked for manual review
- `deferred`: Requires human intervention
- `error`: Resolution failed

## Resolution Strategies

### 1. Low-Confidence Deletion

**Trigger Conditions:**
- One belief has confidence < 0.3 (configurable)
- Neither belief has importance ≥ 0.9
- Clear confidence differential between beliefs

**Process:**
1. Identify lower-confidence belief
2. Verify importance thresholds
3. Mark belief for deletion
4. Update belief registry and memory

**Example:**
```python
# Belief A: confidence=0.15, importance=0.3
# Belief B: confidence=0.85, importance=0.4
# Result: Delete Belief A
```

### 2. Semantic Reframing

**Trigger Conditions:**
- High semantic similarity between belief texts
- Conflict confidence < 0.7 (weak conflict)
- Jaccard similarity ≥ 0.3

**Process:**
1. Analyze semantic similarity using keyword overlap
2. Choose lower-confidence belief for reframing
3. Add qualifying language to reduce absoluteness
4. Update belief with reframed text

**Reframing Patterns:**
- "All X" → "Most X"
- "Never Y" → "Rarely Y"
- "X is Y" → "X might be Y"
- "Z" → "It seems that Z"

**Example:**
```python
# Original: "All AI systems are dangerous"
# Reframed: "Most AI systems are dangerous"
```

### 3. Simulated Dialogue (Theory of Mind)

**Trigger Conditions:**
- Theory of Mind engine available
- Neither low-confidence deletion nor reframing applicable
- Beliefs have moderate-to-high confidence

**Process:**
1. Create agent models representing each belief perspective
2. Simulate perspective-taking and explanation generation
3. Analyze dialogue outcomes for resolution insights
4. Apply resolution or flag for human review

**Example:**
```python
# Agent A believes: "Privacy is more important than security"
# Agent B believes: "Security is more important than privacy"
# Simulation explores nuanced perspectives and potential synthesis
```

### 4. Human Deferral

**Automatic Deferral Triggers:**
- Belief importance ≥ 0.9 (high-importance protection)
- Conflict confidence ≥ 0.8 AND both beliefs confidence ≥ 0.8
- No automatic resolution strategy applicable

**Process:**
1. Flag conflict for human review
2. Preserve all original belief data
3. Log detailed reasoning for deferral
4. Generate human-readable explanation

## Configuration

### Thresholds

```python
# Default configuration constants
MIN_CONFIDENCE_THRESHOLD = 0.3      # Below this: deletion candidates
HIGH_CONFIDENCE_THRESHOLD = 0.8     # Above this: require human review
HIGH_IMPORTANCE_THRESHOLD = 0.9     # Above this: never auto-delete
SEMANTIC_SIMILARITY_THRESHOLD = 0.85 # For reframing detection
DEFAULT_SAMPLE_SIZE = 100           # Max conflicts per pipeline run
```

### Custom Configuration

```python
config = {
    "thresholds": {
        "min_confidence": 0.2,
        "high_confidence": 0.85,
        "high_importance": 0.95,
        "semantic_similarity": 0.8
    },
    "strategies": {
        "enable_deletion": True,
        "enable_reframing": True,
        "enable_dialogue": True,
        "enable_deferral": True
    },
    "limits": {
        "max_sample_size": 200,
        "max_processing_time": 3600  # seconds
    }
}

resolver = ContradictionResolver(config)
```

## Integration

### Journal Engine Integration

The resolver integrates with the journal engine for both input and output:

**Input:**
- Queries journal for `reflexive_contradiction` tagged entries
- Filters for unresolved conflicts
- Parses structured contradiction data

**Output:**
- Logs resolution outcomes with structured metadata
- Tags entries as `conflict_resolved`
- Includes performance metrics and file references

```python
# Journal entry format
{
    "content": "Contradiction resolution pipeline completed. Resolved 15 conflicts.",
    "tags": ["conflict_resolved", "contradiction_resolution_engine"],
    "metadata": {
        "conflicts_processed": 15,
        "beliefs_deleted": 3,
        "beliefs_reframed": 7,
        "log_file": "/workspace/data/logs/resolution_log_2025-01-25.json"
    }
}
```

### Belief Registry Integration

**Operations:**
- Query beliefs for conflict resolution
- Update belief metadata with resolution tags
- Delete low-confidence beliefs
- Preserve original versions before modification

**Belief Modifications:**
```python
# Added to updated beliefs
belief.tags.add('conflict_resolved')
belief.tags.add('reframed')  # if reframed
belief.updated_at = datetime.now()

# Added metadata
belief.conflict_resolved = True
belief.resolution_strategy = 'reframing'
```

### Memory Manager Integration

**Operations:**
- Remove deleted beliefs from memory store
- Update memory entries with reframed content
- Maintain memory consistency with belief registry

### Theory of Mind Integration

**Agent Model Creation:**
```python
# Create perspective advocates
agent_a = tom_engine.create_agent(
    agent_id=f"belief_advocate_a_{conflict_id}",
    name="Belief A Advocate",
    beliefs={belief_id: belief_text}
)

# Simulate perspective-taking
perspective = simulate_perspective(agent_a, {
    "conflicting_belief": opposing_belief_text,
    "task": "explain_and_defend"
})
```

## Logging & Audit Trail

### Log Files

**Resolution Log**: `/workspace/data/logs/resolution_log_YYYY-MM-DD.json`
```json
{
    "timestamp": "2025-01-25T14:30:00Z",
    "pipeline_run": "uuid-12345",
    "total_conflicts": 15,
    "statistics": {
        "conflicts_loaded": 25,
        "conflicts_resolved": 15,
        "beliefs_deleted": 3,
        "beliefs_reframed": 7,
        "conflicts_deferred": 5
    },
    "resolutions": [
        {
            "conflict_id": "conflict-123",
            "action": "deleted",
            "deleted_beliefs": ["belief-456"],
            "explanation": "Low confidence belief removed",
            "confidence": 0.8,
            "strategy_used": "low_confidence_deletion"
        }
    ]
}
```

**Engine Log**: `/workspace/data/logs/contradiction_resolution.log`
- Structured logging with timestamps
- Debug information for troubleshooting
- Performance metrics and timing data

### Reversibility

All resolution actions are designed to be reversible:

1. **Original Preservation**: Complete original belief data saved before modification
2. **Resolution Metadata**: Detailed reasoning and strategy documentation
3. **Audit Trail**: Full log of all decisions and transformations
4. **Human Review**: Flagged items for manual verification

## Performance

### Optimization Guidelines

**Batch Processing:**
```python
# Process conflicts in batches to manage memory
for batch in batch_conflicts(conflicts, batch_size=25):
    batch_results = [resolver.resolve_conflict(pair) for pair in batch]
    resolver._apply_resolutions(batch_results)
```

**Parallel Processing:**
```python
from concurrent.futures import ThreadPoolExecutor

# Resolve conflicts in parallel (for I/O-bound operations)
with ThreadPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(resolver.resolve_conflict, conflicts))
```

**Memory Management:**
- Use sample_size limits for large conflict sets
- Process conflicts in temporal order (newest first)
- Implement conflict deduplication for repeated pairs

### Performance Metrics

**Typical Performance:**
- **Loading**: ~100 conflicts/second from JSON files
- **Prioritization**: ~1000 conflicts/second
- **Resolution**: ~10-50 conflicts/second (depends on strategy complexity)
- **Memory Usage**: ~1MB per 1000 conflicts

**Optimization Targets:**
- Sample size: 100-500 conflicts per run
- Processing time: < 5 minutes for 100 conflicts
- Memory usage: < 50MB for normal operations

## Ethics & Safeguards

### Protection Rules

1. **High-Importance Protection**: Never delete beliefs with importance ≥ 0.9 without human review
2. **Source Filtering**: Only modify beliefs with source = "human" or "system", never "simulated"
3. **Conflict Resolution Marking**: All modified beliefs tagged with resolution metadata
4. **Reversibility**: Complete audit trail enables full reversal of all changes
5. **Human Oversight**: High-confidence conflicts automatically flagged for review

### Safety Mechanisms

**Confidence Thresholds:**
- Deletion requires confidence < 0.3 AND importance < 0.9
- Reframing requires semantic similarity evidence
- High-confidence conflicts (≥0.8) trigger human review

**Metadata Preservation:**
```python
# Required metadata for all resolutions
{
    "conflict_resolved": True,
    "resolution_strategy": "low_confidence_deletion",
    "resolution_timestamp": "2025-01-25T14:30:00Z",
    "original_confidence": 0.15,
    "resolution_confidence": 0.8,
    "human_review_required": False
}
```

## Troubleshooting

### Common Issues

**No Conflicts Found:**
```python
# Check data sources
conflicts = resolver.load_conflicts()
if not conflicts:
    print("Check journal engine and audit file paths")
    print("Verify reflexive contradiction auditor has run")
```

**High Memory Usage:**
```python
# Reduce sample size
report = resolver.run_resolution_pipeline(sample_size=25)
```

**Integration Errors:**
```python
# Check component availability
from contradiction_resolution_engine import (
    BELIEF_REGISTRY_AVAILABLE,
    MEMORY_MANAGER_AVAILABLE,
    JOURNAL_ENGINE_AVAILABLE,
    THEORY_OF_MIND_AVAILABLE
)
print(f"Belief Registry: {BELIEF_REGISTRY_AVAILABLE}")
print(f"Memory Manager: {MEMORY_MANAGER_AVAILABLE}")
print(f"Journal Engine: {JOURNAL_ENGINE_AVAILABLE}")
print(f"Theory of Mind: {THEORY_OF_MIND_AVAILABLE}")
```

### Debug Mode

```python
import logging
logging.getLogger('ContradictionResolutionEngine').setLevel(logging.DEBUG)

# Or via CLI
python3 contradiction_resolution_engine.py --verbose
```

### Log Analysis

```bash
# Monitor real-time resolution activity
tail -f /workspace/data/logs/contradiction_resolution.log

# Search for specific conflict types
grep "low_confidence_deletion" /workspace/data/logs/resolution_log_*.json

# Count resolution outcomes
jq '.resolutions[] | .action' /workspace/data/logs/resolution_log_2025-01-25.json | sort | uniq -c
```

## Examples

### Example 1: Basic Resolution Pipeline

```python
#!/usr/bin/env python3
"""
Basic contradiction resolution example
"""
from contradiction_resolution_engine import ContradictionResolver

def main():
    # Initialize resolver
    resolver = ContradictionResolver()
    
    # Run resolution pipeline
    print("🚀 Starting contradiction resolution...")
    report = resolver.run_resolution_pipeline(sample_size=50)
    
    # Display results
    print(f"✅ Pipeline completed!")
    print(f"   Conflicts processed: {report['total_conflicts_processed']}")
    print(f"   Beliefs deleted: {report['resolution_breakdown']['deleted']}")
    print(f"   Beliefs reframed: {report['resolution_breakdown']['reframed']}")
    print(f"   Human review required: {report['human_review_required']}")
    
    # Show individual results
    for result in report['results'][:5]:  # First 5
        print(f"   {result['conflict_id']}: {result['action']} ({result['strategy_used']})")

if __name__ == "__main__":
    main()
```

### Example 2: Custom Configuration

```python
#!/usr/bin/env python3
"""
Custom configuration example with conservative settings
"""
from contradiction_resolution_engine import ContradictionResolver

def main():
    # Conservative configuration
    config = {
        "min_confidence_threshold": 0.2,  # More aggressive deletion
        "high_confidence_threshold": 0.9,  # Higher bar for human review
        "high_importance_threshold": 0.8,  # Protect more beliefs
    }
    
    resolver = ContradictionResolver(config)
    
    # Load and inspect conflicts before resolution
    conflicts = resolver.load_conflicts()
    print(f"📋 Loaded {len(conflicts)} conflicts")
    
    # Prioritize and show top conflicts
    prioritized = resolver.prioritize_conflicts(conflicts)
    print("\n🔍 Top 3 conflicts by priority:")
    for i, conflict in enumerate(prioritized[:3], 1):
        print(f"   {i}. {conflict.conflict_id} (score: {conflict.priority_score:.3f})")
        print(f"      A: {conflict.get_belief_a_text()[:50]}...")
        print(f"      B: {conflict.get_belief_b_text()[:50]}...")
    
    # Resolve with limited sample
    report = resolver.run_resolution_pipeline(sample_size=10)
    print(f"\n✅ Resolved {report['total_conflicts_processed']} conflicts")

if __name__ == "__main__":
    main()
```

### Example 3: Manual Conflict Resolution

```python
#!/usr/bin/env python3
"""
Manual step-by-step conflict resolution
"""
from contradiction_resolution_engine import ContradictionResolver, BeliefPair

def main():
    resolver = ContradictionResolver()
    
    # Create sample conflict manually
    sample_conflict = BeliefPair(
        belief_a={
            "id": "belief-123",
            "statement": "All AI systems are inherently safe",
            "confidence": 0.25,
            "importance": 0.6
        },
        belief_b={
            "id": "belief-456", 
            "statement": "AI systems pose significant safety risks",
            "confidence": 0.85,
            "importance": 0.8
        },
        conflict_id="manual-test",
        conflict_data={
            "conflict": True,
            "confidence": 0.9,
            "explanation": "Contradictory safety assessments"
        }
    )
    
    # Calculate priority
    priority_score = resolver._calculate_priority_score(sample_conflict)
    print(f"📊 Priority score: {priority_score:.3f}")
    
    # Try different strategies
    print("\n🔧 Testing resolution strategies:")
    
    # Low-confidence deletion
    deletion_result = resolver._try_low_confidence_deletion(sample_conflict)
    if deletion_result:
        print(f"   ✅ Deletion strategy: {deletion_result.explanation}")
    
    # Reframing
    reframe_result = resolver._try_reframing(sample_conflict)
    if reframe_result:
        print(f"   ✅ Reframing strategy: {reframe_result.explanation}")
    
    # Full resolution
    result = resolver.resolve_conflict(sample_conflict)
    print(f"\n🎯 Final resolution: {result.action}")
    print(f"   Strategy: {result.strategy_used}")
    print(f"   Explanation: {result.explanation}")
    print(f"   Confidence: {result.confidence}")

if __name__ == "__main__":
    main()
```

## Version History

- **v1.0.0** (2025-01-25): Initial production release
  - Core resolution strategies implemented
  - Full integration with Axiom belief system
  - Comprehensive test suite and documentation
  - Ethics safeguards and human review workflows

---

*For additional support or feature requests, please consult the Axiom development team or refer to the source code documentation.*