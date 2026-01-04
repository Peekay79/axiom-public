# Belief Confidence Engine Documentation

## Overview

The Belief Confidence Engine is a production-grade system for scoring belief confidence in Axiom's belief system. It provides comprehensive, multi-dimensional confidence scoring that considers source trustworthiness, temporal factors, reinforcement evidence, and alignment with core beliefs.

## Key Features

- **Multi-dimensional scoring**: Considers source trust, age decay, reinforcement frequency, and core belief alignment
- **Vectorized batch processing**: Efficient processing of large belief sets
- **Configurable parameters**: Customizable weights and thresholds
- **Detailed explanations**: Human-readable explanations of confidence calculations
- **Integration-ready**: Seamlessly integrates with existing Axiom systems

## Architecture

### Core Components

#### `BeliefScore` Dataclass
Comprehensive confidence score with supporting metadata and explanations.

```python
@dataclass
class BeliefScore:
    confidence: float                    # Final confidence (0.0-1.0)
    source_trustworthiness: float       # Source reliability score
    reinforcement_frequency: int        # Number of confirmations
    recency_factor: float               # Temporal freshness
    decay_penalty: float                # Age-based decay penalty
    core_belief_alignment: float        # Alignment with core beliefs
    explanation: str                    # Human-readable explanation
    calculation_timestamp: datetime     # When score was calculated
    scoring_version: str                # Engine version
    factors_used: List[str]             # Which factors were applied
    warnings: List[str]                 # Any warnings or concerns
```

#### `BeliefScorer` Class
Advanced belief confidence scoring engine with configurable parameters.

```python
class BeliefScorer:
    def __init__(self, config: Optional[Dict[str, Any]] = None)
    def score_belief(self, belief: Belief, similar_beliefs: Optional[List[Belief]] = None) -> BeliefScore
    def score_belief_batch(self, beliefs: List[Belief]) -> Dict[UUID, BeliefScore]
```

## API Documentation

### Initialization

```python
from belief_confidence_engine import BeliefScorer, score_single_belief

# Use default configuration
scorer = BeliefScorer()

# Use custom configuration
custom_config = {
    "source_weight": 0.3,
    "reinforcement_weight": 0.2,
    "recency_weight": 0.2,
    "decay_weight": 0.15,
    "alignment_weight": 0.15,
    "decay_half_life_days": 45.0
}
scorer = BeliefScorer(custom_config)
```

### Scoring Individual Beliefs

```python
from belief_models import Belief
from datetime import datetime, timezone

belief = Belief(
    statement="AI systems should prioritize human safety",
    belief_type="normative",
    created_at=datetime.now(timezone.utc),
    provenance="user",
    evidence=["doc://safety_guidelines"],
    confidence=0.8,
    importance=0.9,
    tags={"safety", "ethics"}
)

# Score the belief
score = scorer.score_belief(belief)

print(f"Confidence: {score.confidence:.3f}")
print(f"Explanation: {score.explanation}")
print(f"Warnings: {score.warnings}")
```

### Batch Processing

```python
beliefs = [belief1, belief2, belief3, ...]  # List of Belief objects

# Batch scoring for efficiency
scores = scorer.score_belief_batch(beliefs)

for belief_id, score in scores.items():
    print(f"Belief {belief_id}: {score.confidence:.3f}")
```

### Convenience Functions

```python
# Score a single belief with default configuration
score = score_single_belief(belief)

# Enhance belief with confidence metadata
enhanced_belief = enhance_belief_with_confidence_score(belief)
```

## Configuration

### Environment Variables

The engine supports configuration through environment variables:

```bash
# Confidence factor weights (must sum to ≤ 1.0)
export CONFIDENCE_SOURCE_WEIGHT=0.25
export CONFIDENCE_REINFORCEMENT_WEIGHT=0.20
export CONFIDENCE_RECENCY_WEIGHT=0.20
export CONFIDENCE_DECAY_WEIGHT=0.15
export CONFIDENCE_ALIGNMENT_WEIGHT=0.20

# Decay function parameters
export CONFIDENCE_DECAY_HALF_LIFE=30.0
export CONFIDENCE_DECAY_FUNCTION=exponential  # or "linear"

# Core belief alignment
export CONFIDENCE_ALIGNMENT_THRESHOLD=0.3

# Reinforcement parameters
export CONFIDENCE_REINFORCEMENT_BOOST=0.1
export CONFIDENCE_MAX_REINFORCEMENT=0.3
```

### Configuration Dictionary

```python
config = {
    # Weighting coefficients (should sum to 1.0)
    "source_weight": 0.25,           # Source trustworthiness importance
    "reinforcement_weight": 0.20,    # Reinforcement evidence importance  
    "recency_weight": 0.20,          # Temporal freshness importance
    "decay_weight": 0.15,            # Decay penalty importance
    "alignment_weight": 0.20,        # Core belief alignment importance
    
    # Decay function parameters
    "decay_half_life_days": 30.0,    # Half-life for exponential decay
    "decay_function": "exponential",  # "exponential" or "linear"
    
    # Core belief alignment
    "core_beliefs": [                 # List of core belief statements
        "Transparency and honesty are fundamental to trust",
        "Human agency and autonomy must be respected",
        # ... more core beliefs
    ],
    "alignment_threshold": 0.3,       # Minimum similarity for alignment
    
    # Source trustworthiness
    "trusted_sources": [              # Whitelist of trusted sources
        "user", "human", "direct_input", "axiom", 
        "system", "journal_reflection", "verified"
    ],
    
    # Reinforcement tracking
    "reinforcement_boost": 0.1,       # Boost per reinforcement
    "max_reinforcement_bonus": 0.3    # Maximum reinforcement bonus
}
```

## Scoring Factors

### 1. Source Trustworthiness

Evaluates the reliability of the belief's origin:

- **High Trust (0.85-0.92)**: user, human, direct_input, axiom, system
- **Medium Trust (0.58-0.78)**: belief_core, extracted, ai_generated
- **Low Trust (0.25-0.45)**: speculation, unknown, unverified

### 2. Reinforcement Frequency

Counts confirmations and supporting evidence:

- Evidence documents in `belief.evidence`
- Reinforcement tags: "confirmed", "validated", "verified"
- Semantic similarity with other beliefs (when available)

### 3. Recency Factor

Measures temporal freshness (inverse of decay penalty):

```python
recency_factor = 1.0 - decay_penalty
```

### 4. Decay Penalty

Time-based confidence degradation:

**Exponential Decay** (default):
```python
decay_factor = exp(-age_days * ln(2) / half_life_days)
penalty = 1.0 - decay_factor
```

**Linear Decay**:
```python
penalty = min(1.0, age_days / (2 * half_life_days))
```

### 5. Core Belief Alignment

Semantic similarity with fundamental principles:

- Uses sentence transformers when available
- Falls back to keyword-based heuristics
- Considers positive/negative alignment keywords

## Integration Points

### Belief Registry Integration

```python
from belief_registry import BeliefRegistry
from belief_confidence_engine import BeliefScorer

registry = BeliefRegistry()
scorer = BeliefScorer()

# Score beliefs in registry
beliefs = registry.get_all_beliefs()
scores = scorer.score_belief_batch(beliefs)

# Update registry with scores
for belief in beliefs:
    if belief.id in scores:
        score = scores[belief.id]
        # Add confidence metadata to belief
        enhanced_belief = enhance_belief_with_confidence_score(belief)
        registry.update_belief(enhanced_belief)
```

### Journal Engine Integration

```python
from journal_engine import generate_journal_entry

# Log confidence score changes
def log_confidence_update(belief_id, old_score, new_score):
    generate_journal_entry(
        content=f"Belief {belief_id} confidence updated: {old_score:.3f} → {new_score:.3f}",
        tags=["confidence_update", "belief_scoring"],
        source="belief_confidence_engine"
    )
```

### Memory Pruner Integration

```python
def should_prune_belief(belief, score):
    """Determine if belief should be pruned based on confidence score"""
    
    # Never prune protected beliefs
    if belief.is_protected:
        return False
    
    # Prune very low confidence beliefs
    if score.confidence < 0.1:
        return True
    
    # Prune old beliefs with high decay
    if score.decay_penalty > 0.9 and score.confidence < 0.3:
        return True
    
    # Prune beliefs with poor source trust and no reinforcement
    if (score.source_trustworthiness < 0.3 and 
        score.reinforcement_frequency == 0 and 
        score.confidence < 0.4):
        return True
    
    return False
```

## Usage Examples

### Basic Scoring

```python
from belief_confidence_engine import BeliefScorer
from belief_models import Belief
from datetime import datetime, timezone

# Create a scorer
scorer = BeliefScorer()

# Create a belief
belief = Belief(
    statement="Machine learning models require diverse training data",
    belief_type="descriptive",
    created_at=datetime.now(timezone.utc),
    provenance="user",
    evidence=["doc://ml_best_practices", "doc://bias_study"],
    tags={"machine_learning", "data_quality", "verified"}
)

# Score the belief
score = scorer.score_belief(belief)

print(f"""
Belief: {belief.statement}
Confidence: {score.confidence:.3f}
Source Trust: {score.source_trustworthiness:.3f}
Reinforcement: {score.reinforcement_frequency}
Recency: {score.recency_factor:.3f}
Alignment: {score.core_belief_alignment:.3f}

Explanation: {score.explanation}

Warnings: {', '.join(score.warnings) if score.warnings else 'None'}
""")
```

### Batch Processing with Progress Tracking

```python
import logging
from belief_confidence_engine import BeliefScorer

# Configure logging to track progress
logging.basicConfig(level=logging.INFO)

scorer = BeliefScorer()

# Large batch of beliefs
beliefs = load_beliefs_from_database()  # Hypothetical function

print(f"Scoring {len(beliefs)} beliefs...")

# Batch process with automatic progress logging
scores = scorer.score_belief_batch(beliefs)

# Analyze results
high_confidence = [s for s in scores.values() if s.confidence > 0.8]
low_confidence = [s for s in scores.values() if s.confidence < 0.3]
warnings = [s for s in scores.values() if s.warnings]

print(f"""
Results:
- High confidence (>0.8): {len(high_confidence)}
- Low confidence (<0.3): {len(low_confidence)}  
- With warnings: {len(warnings)}
""")
```

### Custom Configuration Example

```python
# Configuration for a research environment
research_config = {
    "source_weight": 0.4,           # Emphasize source quality
    "reinforcement_weight": 0.3,    # Value peer review/citations
    "recency_weight": 0.15,         # Recent papers matter more
    "decay_weight": 0.1,            # Research doesn't age as quickly
    "alignment_weight": 0.05,       # Less emphasis on alignment
    
    "decay_half_life_days": 90.0,   # Longer half-life for research
    "trusted_sources": [
        "peer_reviewed", "researcher", "academic", 
        "verified_publication", "expert_review"
    ],
    "core_beliefs": [
        "Scientific rigor is essential for valid research",
        "Reproducibility is fundamental to scientific progress",
        "Peer review improves research quality"
    ]
}

research_scorer = BeliefScorer(research_config)
```

## Performance Considerations

### Batch Processing Benefits

- **Embedding Pre-calculation**: For large batches, embeddings are calculated once
- **Memory Efficiency**: Vectorized operations reduce memory overhead
- **Progress Tracking**: Built-in logging for long-running operations

### Optimization Tips

1. **Use batch processing** for >10 beliefs
2. **Cache embeddings** when processing similar belief sets repeatedly
3. **Configure logging level** to WARNING in production to reduce overhead
4. **Consider parallel processing** for very large datasets (>1000 beliefs)

### Memory Usage

Approximate memory usage per belief:
- With embeddings: ~2KB per belief
- Without embeddings: ~0.5KB per belief

## Error Handling

### Graceful Degradation

The engine provides robust error handling:

```python
# Missing timestamp - uses current time
belief_no_time = Belief(statement="Test", created_at=None, provenance="user")
score = scorer.score_belief(belief_no_time)  # Works with fallback

# Unknown source - uses default trust
belief_unknown = Belief(statement="Test", provenance="unknown_source")
score = scorer.score_belief(belief_unknown)  # Works with default values

# Embedding failures - falls back to heuristics
# Network issues, model loading failures, etc. are handled gracefully
```

### Error Types and Handling

| Error Type | Handling Strategy |
|------------|------------------|
| Missing timestamps | Use current time with warning |
| Unknown sources | Apply default trust score |
| Empty statements | Assign minimal alignment score |
| Embedding failures | Fall back to keyword heuristics |
| Calculation errors | Return safe default scores |

## Monitoring and Debugging

### Logging Configuration

```python
import logging

# Enable debug logging for development
logging.getLogger("belief_confidence_engine").setLevel(logging.DEBUG)

# Production logging
logging.getLogger("belief_confidence_engine").setLevel(logging.WARNING)
```

### Score Analysis

```python
def analyze_score_distribution(scores):
    """Analyze the distribution of confidence scores"""
    
    confidences = [s.confidence for s in scores.values()]
    
    print(f"""
Score Distribution:
- Mean: {np.mean(confidences):.3f}
- Median: {np.median(confidences):.3f}
- Std Dev: {np.std(confidences):.3f}
- Min: {np.min(confidences):.3f}
- Max: {np.max(confidences):.3f}

Percentiles:
- 25th: {np.percentile(confidences, 25):.3f}
- 75th: {np.percentile(confidences, 75):.3f}
- 90th: {np.percentile(confidences, 90):.3f}
- 95th: {np.percentile(confidences, 95):.3f}
    """)
```

## Testing

The engine includes comprehensive tests:

```bash
# Run all tests
python -m pytest test_belief_confidence_engine.py -v

# Run specific test categories
python -m pytest test_belief_confidence_engine.py::TestBeliefScore -v
python -m pytest test_belief_confidence_engine.py::TestBeliefScorer -v
python -m pytest test_belief_confidence_engine.py::TestScoringEdgeCases -v
```

### Test Coverage

- **30+ test cases** covering all functionality
- **Edge cases**: Empty statements, missing metadata, future timestamps
- **Error handling**: Network failures, calculation errors
- **Integration**: Compatibility with existing Axiom systems
- **Performance**: Batch processing, large datasets

## Future Enhancements

### Planned Features

1. **Dynamic weight learning**: Automatically adjust weights based on outcomes
2. **Belief network analysis**: Consider belief interdependencies
3. **Temporal confidence modeling**: More sophisticated aging models
4. **Multi-modal evidence**: Support for non-text evidence types
5. **Confidence calibration**: Ensure confidence scores are well-calibrated

### Extensibility

The engine is designed for extensibility:

```python
class CustomBeliefScorer(BeliefScorer):
    """Extended scorer with custom factors"""
    
    def _calculate_custom_factor(self, belief):
        """Add your custom scoring logic here"""
        return custom_score
    
    def score_belief(self, belief, similar_beliefs=None):
        # Get base score
        base_score = super().score_belief(belief, similar_beliefs)
        
        # Add custom factor
        custom_factor = self._calculate_custom_factor(belief)
        
        # Recalculate confidence with custom factor
        enhanced_confidence = (
            base_score.confidence * 0.9 + 
            custom_factor * 0.1
        )
        
        # Return enhanced score
        return BeliefScore(
            confidence=enhanced_confidence,
            # ... other fields
            explanation=f"{base_score.explanation} Enhanced with custom factor: {custom_factor:.3f}"
        )
```

## Troubleshooting

### Common Issues

**Low confidence scores across the board**
- Check source trustworthiness mappings
- Verify core belief alignment configuration
- Review decay parameters for your use case

**Inconsistent scoring**
- Ensure consistent belief metadata
- Check for timezone issues in timestamps
- Verify embedding model availability

**Poor performance**
- Use batch processing for multiple beliefs
- Check embedding model loading
- Consider reducing batch size if memory constrained

### Debug Information

```python
# Enable detailed debug output
scorer = BeliefScorer()
scorer.config["debug_mode"] = True

score = scorer.score_belief(belief)

# Check individual factor contributions
print(f"Source contribution: {score.source_trustworthiness * scorer.config['source_weight']:.3f}")
print(f"Recency contribution: {score.recency_factor * scorer.config['recency_weight']:.3f}")
# ... etc
```

## Conclusion

The Belief Confidence Engine provides a robust, scalable solution for belief confidence scoring in Axiom. Its multi-dimensional approach, comprehensive error handling, and integration capabilities make it suitable for production use in complex belief systems.

For additional support or feature requests, consult the test suite and integration examples, or refer to the Axiom development team.