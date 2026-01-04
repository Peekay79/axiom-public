# Belief Registry Documentation

## Overview

The Belief Registry is an enhanced belief management system that provides semantic contradiction detection using Natural Language Inference (NLI) to maintain coherent and consistent belief systems. It automatically detects, flags, and manages conflicting beliefs to ensure system integrity and cognitive coherence.

## Architecture

### Core Components

1. **Semantic Conflict Detection Engine**: Uses NLI-based analysis to identify contradictory beliefs
2. **Belief Validation Pipeline**: Processes new beliefs through conflict detection workflows
3. **Tagging and Metadata System**: Automatically labels beliefs based on conflict analysis
4. **Journal Engine Integration**: Logs conflict events for audit and review
5. **Performance Optimization**: Handles large belief sets efficiently

### Integration Points

- **NLI Conflict Checker**: `nli_conflict_checker.py` for semantic analysis
- **Memory Manager**: `memory_manager.py` for belief storage and retrieval
- **Journal Engine**: `journal_engine.py` for event logging (optional)
- **Belief Models**: `belief_models.py` for structured belief representation

## Features

### Semantic Conflict Detection

The system uses advanced NLI (Natural Language Inference) to detect semantic contradictions between beliefs:

```python
from belief_registry import add_belief_with_conflict_detection, check_belief_conflicts
from belief_models import Belief
from memory_manager import Memory

# Create a new belief
new_belief = Belief(
    statement="The sky is never blue",
    confidence=0.8
)

# Add with conflict detection
memory = Memory()
success, conflicts = await add_belief_with_conflict_detection(memory, new_belief)

if not success:
    print(f"Belief rejected due to {len(conflicts)} conflicts")
```

### Confidence Thresholds

The system uses configurable confidence thresholds for decision making:

- **High Confidence (≥0.8)**: Automatic rejection with `rejected_due_to_conflict` tag
- **Medium Confidence (0.6-0.8)**: Flagged for human review with `requires_human_review` tag
- **Low Confidence (<0.6)**: Accepted with monitoring

### Automated Tagging System

Beliefs are automatically tagged based on conflict analysis:

#### Rejection Tags
- `rejected_due_to_conflict`: High-confidence semantic conflict detected
- `semantic_conflict_detected`: General conflict detection flag
- `conflict_confidence_XX`: Numeric confidence score (e.g., `conflict_confidence_85`)

#### Review Tags
- `requires_human_review`: Medium-confidence conflict requiring review
- `semantic_conflict_potential`: Potential conflict flag

### Journal Engine Integration

All conflict events are logged for audit and review:

```python
# Conflict events are automatically logged with structured metadata
{
    "belief_id": "uuid-of-belief",
    "conflict_count": 2,
    "highest_confidence": 0.85,
    "action_taken": "rejected",
    "detection_timestamp": "2025-01-25T10:30:00Z",
    "thresholds": {
        "rejection_threshold": 0.8,
        "review_threshold": 0.6
    }
}
```

## API Reference

### Core Functions

#### `add_belief_with_conflict_detection(memory, belief)`

Adds a belief to memory after performing semantic conflict detection.

**Parameters:**
- `memory`: Memory manager instance
- `belief`: Belief object to add

**Returns:**
- `Tuple[bool, List[BeliefConflictResult]]`: Success status and detected conflicts

**Example:**
```python
memory = Memory()
belief = Belief(statement="Python is the best programming language")
success, conflicts = await add_belief_with_conflict_detection(memory, belief)

if conflicts:
    print(f"Detected {len(conflicts)} potential conflicts")
    for conflict in conflicts:
        print(f"- Confidence: {conflict.confidence:.3f}")
        print(f"- Explanation: {conflict.explanation}")
```

#### `check_belief_conflicts(belief_text, memory=None)`

Checks for conflicts without adding the belief to memory.

**Parameters:**
- `belief_text`: Text of the belief to check
- `memory`: Optional memory instance

**Returns:**
- `List[BeliefConflictResult]`: List of detected conflicts

**Example:**
```python
conflicts = await check_belief_conflicts("The Earth is flat")
if conflicts:
    print(f"This belief would conflict with {len(conflicts)} existing beliefs")
```

#### `detect_semantic_conflicts(new_belief, existing_beliefs)`

Core conflict detection function using NLI analysis.

**Parameters:**
- `new_belief`: Belief object to check
- `existing_beliefs`: List of existing beliefs to compare against

**Returns:**
- `List[BeliefConflictResult]`: Sorted list of conflicts (highest confidence first)

#### `run_registry_pass()`

Runs a complete registry pass with conflict detection on all beliefs.

**Returns:**
- `Dict`: Results including conflict statistics

**Example:**
```python
result = await run_registry_pass()
print(f"Processed: {result['conflict_stats']['total_processed']} beliefs")
print(f"Rejected: {result['conflict_stats']['beliefs_rejected']} beliefs")
print(f"Flagged: {result['conflict_stats']['beliefs_flagged']} beliefs")
```

### Configuration Functions

#### `get_conflict_detection_stats()`

Returns current configuration and system status.

**Returns:**
- `Dict`: Configuration statistics

**Example:**
```python
stats = get_conflict_detection_stats()
print(f"Rejection threshold: {stats['conflict_confidence_threshold']}")
print(f"Review threshold: {stats['human_review_threshold']}")
print(f"Journal engine available: {stats['journal_engine_available']}")
```

### Data Classes

#### `BeliefConflictResult`

Represents the result of conflict detection between two beliefs.

**Attributes:**
- `conflicting_belief_id`: ID of the conflicting belief
- `conflict`: Boolean indicating if conflict was detected
- `confidence`: Confidence score (0.0-1.0)
- `explanation`: Human-readable explanation
- `timestamp`: Detection timestamp

**Methods:**
- `should_reject()`: Returns True if confidence ≥ rejection threshold
- `requires_review()`: Returns True if confidence is in review range

## Configuration

### Environment Variables

```bash
# Optional: Override default confidence thresholds
export BELIEF_CONFLICT_THRESHOLD=0.8
export BELIEF_REVIEW_THRESHOLD=0.6

# Optional: Performance tuning
export BELIEF_MAX_COMPARISONS=1000
```

### Runtime Configuration

Configuration constants can be modified at runtime:

```python
import belief_registry

# Adjust thresholds (not recommended in production)
belief_registry.CONFLICT_CONFIDENCE_THRESHOLD = 0.75
belief_registry.HUMAN_REVIEW_CONFIDENCE_THRESHOLD = 0.55
```

## Performance Considerations

### Optimization Features

1. **Comparison Limits**: Maximum of 1000 beliefs compared per new belief
2. **Early Termination**: Stops on first high-confidence conflict for rejections
3. **Batch Processing**: Efficient processing during registry passes
4. **Caching**: NLI model is cached for subsequent calls

### Performance Metrics

- **Small Systems** (<100 beliefs): ~50-100ms per belief addition
- **Medium Systems** (100-1000 beliefs): ~200-500ms per belief addition  
- **Large Systems** (>1000 beliefs): ~500ms-1s per belief addition (with limits)

### Scaling Recommendations

For systems with >10,000 beliefs:
1. Consider implementing belief clustering
2. Use relevance-based pre-filtering
3. Implement distributed conflict detection
4. Cache frequent conflict checks

## Error Handling

### Graceful Degradation

The system is designed to handle failures gracefully:

1. **NLI Failures**: Falls back to string-based analysis
2. **Memory Errors**: Logs errors and continues processing
3. **Journal Failures**: Continues operation with fallback logging
4. **Invalid Beliefs**: Skips invalid entries with warning logs

### Error Recovery

```python
try:
    success, conflicts = await add_belief_with_conflict_detection(memory, belief)
except Exception as e:
    logger.error(f"Conflict detection failed: {e}")
    # Fallback to adding belief without conflict detection
    memory.add_to_long_term(belief.model_dump())
```

## Monitoring and Logging

### Structured Logging

All operations use structured logging with consistent formats:

```
[2025-01-25 10:30:00] [INFO] belief_registry: 📊 Belief conflict event: rejected | 
Belief: abc-123 | Conflicts: 2 | Max confidence: 0.850 | 
Explanation: Semantic contradiction detected
```

### Log Levels

- **INFO**: Normal operations, conflict decisions, statistics
- **WARNING**: Belief rejections, performance warnings
- **ERROR**: System failures, processing errors
- **DEBUG**: Detailed conflict analysis (enable for troubleshooting)

### Metrics Collection

Key metrics are automatically collected:

```python
# Access conflict statistics
result = await run_registry_pass()
metrics = result["conflict_stats"]

print(f"Conflict Detection Rate: {metrics['conflicts_detected'] / metrics['total_processed']:.2%}")
print(f"Rejection Rate: {metrics['beliefs_rejected'] / metrics['total_processed']:.2%}")
```

## Integration Patterns

### Basic Integration

```python
from belief_registry import add_belief_with_conflict_detection
from belief_models import Belief
from memory_manager import Memory

async def add_user_belief(statement: str, confidence: float = 0.7):
    """Add a user-provided belief with conflict detection."""
    belief = Belief(
        statement=statement,
        confidence=confidence,
        provenance="user_input",
        tags={"user_generated"}
    )
    
    memory = Memory()
    success, conflicts = await add_belief_with_conflict_detection(memory, belief)
    
    if not success:
        return {
            "status": "rejected",
            "reason": "semantic_conflict",
            "conflicts": len(conflicts),
            "explanation": conflicts[0].explanation if conflicts else None
        }
    elif conflicts:
        return {
            "status": "flagged",
            "reason": "requires_review",
            "conflicts": len(conflicts)
        }
    else:
        return {
            "status": "accepted",
            "belief_id": str(belief.id)
        }
```

### Batch Processing Integration

```python
async def process_belief_batch(belief_statements: List[str]):
    """Process multiple beliefs with conflict detection."""
    results = []
    memory = Memory()
    
    for statement in belief_statements:
        belief = Belief(statement=statement)
        success, conflicts = await add_belief_with_conflict_detection(memory, belief)
        
        results.append({
            "statement": statement,
            "success": success,
            "conflicts": len(conflicts),
            "action": "rejected" if not success else "accepted"
        })
    
    return results
```

### Review Queue Integration

```python
async def get_beliefs_requiring_review():
    """Get beliefs flagged for human review."""
    memory = Memory()
    all_entries = memory.snapshot()
    
    review_beliefs = []
    for entry in all_entries:
        if entry.get("type") == "belief":
            belief = Belief(**entry)
            if "requires_human_review" in belief.tags:
                review_beliefs.append({
                    "id": str(belief.id),
                    "statement": belief.statement,
                    "confidence": belief.confidence,
                    "flagged_at": belief.updated_at,
                    "tags": list(belief.tags)
                })
    
    return review_beliefs
```

## Testing

### Running Tests

```bash
# Run all belief registry tests
python test_belief_registry.py

# Run specific test categories
python test_belief_registry.py TestBeliefRegistry.test_detect_semantic_conflicts
python test_belief_registry.py TestBeliefRegistryIntegration

# Run with verbose output
python test_belief_registry.py -v
```

### Test Coverage

The test suite covers:

- ✅ Semantic conflict detection with various confidence levels
- ✅ Belief rejection and flagging workflows
- ✅ Tag application and metadata handling
- ✅ Journal engine integration
- ✅ Performance limits and optimization
- ✅ Error handling and edge cases
- ✅ Integration with memory manager
- ✅ Batch processing scenarios

### Example Test Cases

```python
# Test case 1: High-confidence conflict (rejection)
belief_1 = Belief(statement="The sky is blue")
belief_2 = Belief(statement="The sky is never blue")
# Expected: belief_2 rejected with high confidence

# Test case 2: Medium-confidence conflict (review)
belief_1 = Belief(statement="Python is good for data science")
belief_2 = Belief(statement="Python is not suitable for data science")
# Expected: belief_2 flagged for review

# Test case 3: Low-confidence conflict (acceptance)
belief_1 = Belief(statement="Coffee is energizing")
belief_2 = Belief(statement="Tea is relaxing")
# Expected: belief_2 accepted (different topics)
```

## Troubleshooting

### Common Issues

#### 1. High Memory Usage

**Problem**: Memory consumption grows with belief count
**Solution**: 
```python
# Check current belief count
memory = Memory()
belief_count = len([m for m in memory.snapshot() if m.get("type") == "belief"])
print(f"Current belief count: {belief_count}")

# Consider archiving old beliefs if > 10,000
if belief_count > 10000:
    # Implement belief archiving strategy
    pass
```

#### 2. Slow Conflict Detection

**Problem**: Conflict detection takes too long
**Solution**:
```python
# Check performance stats
stats = get_conflict_detection_stats()
print(f"Max comparisons: {stats['max_beliefs_compared']}")

# Reduce comparison limit if needed
import belief_registry
belief_registry.MAX_BELIEFS_TO_COMPARE = 500  # Reduce from 1000
```

#### 3. NLI Model Loading Issues

**Problem**: Sentence transformers model fails to load
**Solution**:
```python
# Check NLI health
from nli_conflict_checker import check_nli_health
health = check_nli_health()
print(f"Model loaded: {health['model_loaded']}")
print(f"Test passed: {health['test_passed']}")

# Manual model download if needed
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
```

#### 4. Journal Engine Connection Issues

**Problem**: Journal engine not available or failing
**Solution**:
```python
# Check journal availability
stats = get_conflict_detection_stats()
if not stats['journal_engine_available']:
    print("Journal engine not available - using fallback logging")
    # System will continue to work with fallback logging
```

### Health Checks

```python
async def system_health_check():
    """Comprehensive health check for belief registry system."""
    results = {}
    
    # Check NLI system
    from nli_conflict_checker import check_nli_health
    results['nli'] = check_nli_health()
    
    # Check memory system
    try:
        memory = Memory()
        memory.snapshot()
        results['memory'] = {'status': 'healthy'}
    except Exception as e:
        results['memory'] = {'status': 'error', 'error': str(e)}
    
    # Check conflict detection config
    results['config'] = get_conflict_detection_stats()
    
    # Test basic conflict detection
    try:
        conflicts = await check_belief_conflicts("Test belief")
        results['conflict_detection'] = {'status': 'healthy', 'test_completed': True}
    except Exception as e:
        results['conflict_detection'] = {'status': 'error', 'error': str(e)}
    
    return results
```

## Future Enhancements

### Planned Features

1. **Belief Clustering**: Group similar beliefs to improve performance
2. **Confidence Learning**: ML-based confidence threshold optimization
3. **Temporal Conflict Detection**: Handle time-sensitive contradictions
4. **Multi-language Support**: Conflict detection across languages
5. **Distributed Processing**: Scale to very large belief systems

### Extension Points

The system is designed for extensibility:

```python
# Custom conflict detection strategies
class CustomConflictDetector:
    async def detect_conflicts(self, new_belief, existing_beliefs):
        # Implement custom logic
        pass

# Custom tagging strategies
def custom_tag_applicator(belief, conflicts):
    # Apply domain-specific tags
    pass

# Integration with external systems
async def external_review_system(flagged_beliefs):
    # Send to external review system
    pass
```

## Security Considerations

### Input Validation

- All belief statements are validated for length and content
- Belief confidence scores are bounded to [0.0, 1.0]
- Memory operations are protected against injection attacks

### Access Control

```python
# Example: Role-based belief management
def check_belief_permissions(user_role: str, action: str) -> bool:
    permissions = {
        "admin": ["create", "update", "delete", "review"],
        "user": ["create"],
        "viewer": ["read"]
    }
    return action in permissions.get(user_role, [])
```

### Audit Trail

All belief operations are logged with:
- User identification (when available)
- Timestamp and action taken
- Conflict analysis results
- System state changes

---

*Last Updated: 2025-01-25*  
*Version: 2.0.0*  
*Author: Axiom AI Systems Team*