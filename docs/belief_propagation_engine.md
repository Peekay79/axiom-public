# Belief Propagation Engine

## Overview

The Belief Propagation Engine is a production-grade system that performs logical, semantic, and causal propagation of belief changes through Axiom's belief network. When new beliefs are added or existing beliefs are modified, the engine analyzes relationships, propagates confidence changes, detects cognitive dissonance, and infers implicit goals from belief clusters.

## Core Architecture

### BeliefPropagationEngine Class

The main engine class coordinates all propagation activities:

```python
from belief_propagation_engine import BeliefPropagationEngine
from belief_models import Belief

# Initialize the engine
engine = BeliefPropagationEngine(memory=memory_instance)

# Add a belief and propagate its effects
belief = Belief(statement="AI systems should prioritize human safety", confidence=0.9)
result = await engine.add_belief(belief)
```

### Data Structures

#### PropagationResult
Contains detailed information about a propagation operation:
- `source_belief_id`: The belief that triggered propagation
- `affected_beliefs`: List of belief IDs that were affected
- `confidence_changes`: Mapping of belief IDs to new confidence values
- `new_dependencies`: List of relationships discovered during propagation
- `propagation_type`: Type of propagation performed
- `metadata`: Additional context and statistics

#### BeliefDependency
Represents relationships between beliefs:
- `source_belief_id`: Source belief in the relationship
- `target_belief_id`: Target belief in the relationship
- `dependency_type`: "causal", "semantic", "logical", or "temporal"
- `strength`: Relationship strength (0.0 to 1.0)
- `explanation`: Human-readable description of the relationship

#### InferredGoal
Goals detected from belief clusters:
- `goal_statement`: Natural language description of the goal
- `supporting_beliefs`: List of belief IDs that support this goal
- `confidence`: Confidence in the goal inference
- `inference_method`: Method used to infer the goal

#### CognitiveDissonanceEvent
Detected contradictions between beliefs:
- `target_belief_id`: Belief experiencing dissonance
- `conflicting_beliefs`: List of beliefs causing the conflict
- `dissonance_strength`: Magnitude of the conflict
- `conflict_type`: "semantic", "value", "logical", or "causal"
- `resolution_suggestions`: Suggested approaches to resolve the conflict

## Propagation Algorithm

### 1. Relationship Discovery

When a new belief is added, the engine discovers relationships through multiple methods:

#### Semantic Similarity
Uses sentence transformers to compute semantic similarity between belief statements:
- Threshold: 0.75 (configurable via `SEMANTIC_SIMILARITY_THRESHOLD`)
- Creates semantic dependencies between highly similar beliefs
- Enables confidence amplification for related beliefs

#### Causal Relationships
Detects causal links through:
- **Existing causal links**: Uses pre-defined causal relationships in belief metadata
- **Heuristic detection**: Scans for causal keywords ("because", "therefore", "leads to", etc.)
- **Semantic boost**: High semantic similarity strengthens causal detection

#### Logical Entailment
Identifies logical relationships via pattern matching:
- **If-then patterns**: "If X then Y" → logical dependency
- **Implication patterns**: "X implies Y" → logical dependency
- **Entailment keywords**: "means", "entails", "necessitates"

### 2. Confidence Propagation and Amplification

#### Non-Linear Confidence Boost
The engine applies confidence amplification using the formula:

```
boost_factor = 1.0 + (cluster_agreement × trust_factor × CONFIDENCE_AMPLIFICATION_FACTOR) / (1 + exp(-reinforcement_count))
boosted_confidence = min(CONFIDENCE_SATURATION_LIMIT, original_confidence × boost_factor)
```

Where:
- `cluster_agreement`: Average semantic similarity weighted by confidence
- `trust_factor`: Average importance of reinforcing beliefs
- `reinforcement_count`: Number of supporting beliefs
- `CONFIDENCE_SATURATION_LIMIT`: Maximum allowed confidence (0.95)

#### Recurrent Reinforcement Tracking
The engine tracks confidence boosts over time:
- Records each boost event with metadata
- Prevents runaway confidence increases
- Maintains provenance for audit trails

### 3. Cycle Detection and Safety Limits

#### Cycle Prevention
- Maintains a cycle detection stack during propagation
- Prevents infinite recursion in circular belief dependencies
- Returns early with "cycle_prevented" result type

#### Depth Limits
- Maximum propagation depth: 5 levels (configurable)
- Performance limits for large belief sets (1000 comparisons max)
- Timeout protection for long-running operations

## Confidence Flow and Saturation Rules

### Amplification Conditions
Confidence is amplified when:
1. **High Semantic Similarity**: Beliefs with similarity > 0.75
2. **Trusted Sources**: Reinforcing beliefs with importance > 0.7
3. **Multiple Reinforcement**: Multiple beliefs support the same conclusion
4. **High Source Confidence**: Reinforcing beliefs have high confidence

### Saturation Prevention
- **Hard Limit**: Confidence cannot exceed 0.95
- **Diminishing Returns**: Sigmoid function reduces boost effectiveness with many reinforcements
- **Trust Gating**: Low-importance beliefs provide minimal amplification

### Confidence History
Each boost is recorded with:
- Original and boosted confidence values
- Boost factor and reinforcement count
- Cluster agreement and trust metrics
- Timestamp for temporal analysis

## Cognitive Dissonance Detection

### Detection Theory
Cognitive dissonance occurs when a belief experiences contradictory pressure from multiple sources. The engine detects this through:

#### Semantic Contradictions
- High semantic similarity with negation patterns
- Keywords: "not", "never", "cannot", "impossible", "false"
- Threshold: Similarity > 0.75 with opposing semantic content

#### Value Conflicts
Detects conflicts between fundamental values:
- **Harm vs Compassion**: "harm", "violence" vs "care", "protect"
- **Freedom vs Control**: "liberty", "autonomy" vs "restrict", "regulate"  
- **Truth vs Deception**: "honest", "transparent" vs "lie", "deceive"

#### Logical Contradictions
- Conflicting logical premises
- Contradictory causal chains
- Incompatible if-then relationships

### Dissonance Strength Calculation
```
dissonance_strength = Σ(similarity × affecting_confidence × dependency_strength)
```

Dissonance is flagged when:
- Strength > 0.8 (configurable via `DISSONANCE_THRESHOLD`)
- Multiple conflicting beliefs present
- High-confidence opposing beliefs

### Resolution Suggestions
The engine generates context-aware suggestions:
- **Semantic**: Refine statements for clarity
- **Value**: Explore contextual balance between values
- **Logical**: Review premises and assumptions
- **Causal**: Examine causal chains for missing steps

## Goal Inference Methodology

### Intent Pattern Detection
The engine scans for goal-indicating patterns:
- **Intent Keywords**: "want", "desire", "hope", "wish", "prefer"
- **Obligation Keywords**: "should", "must", "need"
- **Outcome Keywords**: "achieve", "accomplish", "improve", "enhance"

### Belief Clustering
Goals are inferred from semantically similar belief clusters:
1. **Pattern Matching**: Identify beliefs with intent/outcome patterns
2. **Semantic Clustering**: Group similar beliefs using embeddings
3. **Threshold**: Similarity > 0.7 for goal clustering
4. **Minimum Cluster Size**: At least 2 beliefs required

### Goal Statement Generation
- Extract common themes from belief cluster
- Filter stop words and low-value terms
- Identify action words for goal specificity
- Generate natural language goal statements

### Confidence Calculation
Goal confidence is derived from:
- Average confidence of supporting beliefs (× 0.8 for conservatism)
- Cluster size and semantic coherence
- Quality of detected patterns

## Integration Points

### Journal Engine Integration
All significant events are logged to the journal engine:

#### Propagation Events
```python
await generate_journal_entry(
    content="Belief propagation: comprehensive",
    tags=["belief_propagation", "propagation_event"],
    metadata={
        "belief_id": str(belief.id),
        "affected_beliefs_count": len(affected_beliefs),
        "propagation_depth": result.propagation_depth
    }
)
```

#### Dissonance Events
```python
await generate_journal_entry(
    content="Cognitive dissonance detected: semantic",
    tags=["cognitive_dissonance", "needs_resolution"],
    metadata={
        "target_belief_id": str(dissonance.target_belief_id),
        "dissonance_strength": dissonance.dissonance_strength,
        "resolution_suggestions": dissonance.resolution_suggestions
    }
)
```

#### Goal Inference Events
```python
await generate_journal_entry(
    content="Goal inferred: Improve AI safety standards",
    tags=["goal_inference", "inferred_goal"],
    metadata={
        "goal_statement": goal.goal_statement,
        "supporting_beliefs": goal.supporting_beliefs,
        "confidence": goal.confidence
    }
)
```

### Memory Manager Integration
The engine integrates with the Memory Manager:
- Retrieves existing beliefs for relationship analysis
- Stores propagation results and metadata
- Respects memory access patterns and security constraints

### Belief Registry Integration
Works with the belief registry for:
- Conflict detection during belief addition
- Metadata enrichment with propagation history
- Structured logging of belief lifecycle events

## Configuration

### Environment Variables
```bash
# Propagation limits
MAX_PROPAGATION_DEPTH=5
MAX_BELIEFS_TO_COMPARE=1000

# Similarity thresholds
SEMANTIC_SIMILARITY_THRESHOLD=0.75
CAUSAL_STRENGTH_THRESHOLD=0.6

# Confidence amplification
CONFIDENCE_AMPLIFICATION_FACTOR=1.2
CONFIDENCE_SATURATION_LIMIT=0.95
TRUST_THRESHOLD=0.7

# Feature toggles
GOAL_INFERENCE_ENABLED=true
DISSONANCE_THRESHOLD=0.8

# Model configuration
PROPAGATION_EMBED_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

### Runtime Configuration
The engine supports runtime configuration through constructor parameters:
```python
engine = BeliefPropagationEngine(
    memory=custom_memory,
    embedding_model=custom_model,
    max_depth=3,
    similarity_threshold=0.8
)
```

## Performance Considerations

### Computational Complexity
- **Semantic Similarity**: O(n) for n existing beliefs
- **Relationship Detection**: O(n) per belief added
- **Clustering**: O(n²) worst case for goal inference
- **Dissonance Detection**: O(k) for k affecting beliefs

### Optimization Strategies
1. **Embedding Caching**: Cache semantic embeddings for repeated computations
2. **Similarity Indexing**: Use approximate nearest neighbor search for large belief sets
3. **Lazy Evaluation**: Defer expensive computations until needed
4. **Batch Processing**: Process multiple beliefs together when possible

### Memory Usage
- **Dependency Graph**: Grows with O(n×k) where k is average relationships per belief
- **Confidence History**: Unbounded growth, periodic cleanup recommended
- **Event Storage**: Configurable retention for dissonance and goal events

## Monitoring and Observability

### Metrics
The engine provides metrics for monitoring:
- Propagation latency and throughput
- Relationship discovery rates
- Confidence amplification frequency
- Dissonance detection rates
- Goal inference success rates

### Logging
Structured logging includes:
- **INFO**: Successful propagations and discoveries
- **WARNING**: Dissonance detection and resolution needs
- **ERROR**: Failed operations and exception details
- **DEBUG**: Detailed relationship analysis and intermediate results

### Health Checks
- Embedding model availability
- Memory manager connectivity
- Journal engine integration status
- Performance threshold monitoring

## Troubleshooting

### Common Issues

#### No Relationships Detected
- Check embedding model availability
- Verify similarity thresholds are appropriate
- Ensure beliefs have sufficient semantic content

#### Low Confidence Amplification
- Verify trust thresholds for reinforcing beliefs
- Check importance values in belief metadata
- Review semantic similarity calculations

#### Missing Dissonance Detection
- Confirm dissonance threshold configuration
- Check for proper negation pattern detection
- Verify value conflict pattern matching

#### Goal Inference Failures
- Ensure `GOAL_INFERENCE_ENABLED=true`
- Check for sufficient intent/outcome patterns
- Verify minimum cluster size requirements

### Performance Issues

#### Slow Propagation
- Reduce `MAX_BELIEFS_TO_COMPARE` for large datasets
- Consider approximate similarity algorithms
- Enable embedding caching

#### Memory Growth
- Implement periodic cleanup of old events
- Set retention policies for confidence history
- Monitor dependency graph size

## API Reference

### Core Methods

#### `add_belief(belief: Belief) -> PropagationResult`
Main propagation method that:
1. Discovers relationships with existing beliefs
2. Applies confidence amplification
3. Detects cognitive dissonance
4. Infers goals from belief clusters
5. Returns comprehensive propagation results

#### `get_belief_dependencies(belief_id: UUID) -> List[BeliefDependency]`
Returns all dependency relationships for a specific belief.

#### `get_confidence_history(belief_id: UUID) -> List[ConfidenceBoost]`
Returns confidence amplification history for a belief.

#### `get_recent_dissonance_events(hours: int = 24) -> List[CognitiveDissonanceEvent]`
Returns dissonance events from the specified time window.

#### `get_inferred_goals(min_confidence: float = 0.0) -> List[InferredGoal]`
Returns inferred goals above the confidence threshold.

#### `clear_caches()`
Clears propagation caches and temporary data.

### Utility Methods

#### `_compute_semantic_similarity(belief1: Belief, belief2: Belief) -> float`
Computes semantic similarity between two beliefs using sentence transformers.

#### `_detect_causal_relationships(source: Belief, target: Belief) -> Optional[BeliefDependency]`
Detects causal relationships using existing links and heuristics.

#### `_detect_cognitive_dissonance(target: Belief, affecting: List[Tuple[Belief, BeliefDependency]]) -> Optional[CognitiveDissonanceEvent]`
Analyzes affecting beliefs for contradictory pressure on target belief.

## Best Practices

### Belief Design
- Use clear, unambiguous statement language
- Include appropriate confidence and importance values
- Add meaningful tags for relationship discovery
- Specify provenance for trust calculations

### Performance Optimization
- Batch belief additions when possible
- Monitor memory usage in large deployments
- Use appropriate similarity thresholds for domain
- Implement periodic cleanup of historical data

### Dissonance Management
- Review dissonance events regularly
- Implement resolution workflows
- Track resolution effectiveness
- Use dissonance for belief quality improvement

### Goal Integration
- Connect inferred goals to planning systems
- Track goal achievement and evolution
- Use goal confidence for prioritization
- Maintain goal-belief relationship integrity

## Future Enhancements

### Planned Features
1. **Temporal Propagation**: Time-based relationship decay and evolution
2. **Hierarchical Clustering**: Multi-level belief organization
3. **Advanced NLP**: Enhanced relationship detection with modern language models
4. **Distributed Processing**: Scale to larger belief networks
5. **Interactive Resolution**: GUI for dissonance resolution

### Research Directions
- Causal inference improvements
- Adaptive threshold learning
- Cross-domain belief transfer
- Uncertainty quantification
- Explainable relationship discovery