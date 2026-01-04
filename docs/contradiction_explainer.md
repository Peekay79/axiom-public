# Contradiction Explainer Documentation

## Overview

The Contradiction Explainer is an advanced natural language processing system that provides comprehensive explanations of conflicts between beliefs in Axiom's belief system. It identifies conflict types, extracts relevant keywords, suggests resolution strategies, and generates follow-up questions for clarification.

## Key Features

- **Multi-dimensional conflict analysis**: Semantic, temporal, scope, definitional, and value-based conflicts
- **Natural language explanations**: Human-readable conflict descriptions  
- **Keyword extraction**: Identifies specific terms and concepts in conflict
- **Resolution suggestions**: Actionable strategies for resolving conflicts
- **Follow-up questions**: Guided inquiry for deeper understanding
- **NLI integration**: Leverages natural language inference for semantic analysis
- **Batch processing**: Efficient analysis of multiple conflict pairs

## Architecture

### Core Components

#### `ConflictExplanation` Dataclass
Comprehensive conflict analysis with structured metadata and suggestions.

```python
@dataclass
class ConflictExplanation:
    explanation: str                    # Natural language explanation
    keywords_in_conflict: List[str]     # Conflicting terms/concepts
    suggested_reframe: str              # Reframing suggestion
    follow_up_questions: List[str]      # Clarification questions
    conflict_type: str                  # Type of conflict detected
    severity: str                       # Conflict severity (soft/medium/hard)
    confidence: float                   # Explanation confidence (0.0-1.0)
    semantic_similarity: float          # Semantic similarity score
    nli_conflict_score: Optional[float] # NLI conflict confidence
    belief_metadata_diff: Dict[str, Any] # Metadata differences
    resolution_strategies: List[str]    # Resolution approaches
    requires_human_input: bool          # Whether human review is needed
    analysis_timestamp: datetime        # When analysis was performed
    explanation_version: str            # Explainer version
```

#### `ContradictionExplainer` Class
Advanced contradiction analysis engine with configurable parameters.

```python
class ContradictionExplainer:
    def __init__(self, config: Optional[Dict[str, Any]] = None)
    def explain_conflict(self, belief1: Belief, belief2: Belief) -> ConflictExplanation
```

## API Documentation

### Initialization

```python
from contradiction_explainer import ContradictionExplainer, explain_single_conflict

# Use default configuration
explainer = ContradictionExplainer()

# Use custom configuration
custom_config = {
    "semantic_similarity_threshold": 0.8,
    "hard_conflict_threshold": 0.9,
    "max_keywords_extracted": 8,
    "max_follow_up_questions": 3,
    "explanation_detail_level": "comprehensive"
}
explainer = ContradictionExplainer(custom_config)
```

### Analyzing Single Conflicts

```python
from belief_models import Belief
from datetime import datetime, timezone

belief1 = Belief(
    statement="AI systems should always prioritize human safety",
    belief_type="normative",
    created_at=datetime.now(timezone.utc),
    provenance="user",
    confidence=0.9,
    importance=0.9,
    tags={"safety", "ethics"}
)

belief2 = Belief(
    statement="AI systems should sometimes prioritize efficiency over safety",
    belief_type="normative", 
    created_at=datetime.now(timezone.utc),
    provenance="system",
    confidence=0.6,
    importance=0.7,
    tags={"efficiency", "optimization"}
)

# Analyze the conflict
explanation = explainer.explain_conflict(belief1, belief2)

print(f"Conflict Type: {explanation.conflict_type}")
print(f"Severity: {explanation.severity}")
print(f"Explanation: {explanation.explanation}")
print(f"Keywords: {explanation.keywords_in_conflict}")
print(f"Suggested Reframe: {explanation.suggested_reframe}")
print(f"Follow-up Questions: {explanation.follow_up_questions}")
```

### Batch Processing

```python
belief_pairs = [
    (belief1, belief2),
    (belief3, belief4),
    # ... more pairs
]

explanations = batch_explain_conflicts(belief_pairs)

for i, explanation in enumerate(explanations):
    print(f"Conflict {i+1}: {explanation.conflict_type} ({explanation.severity})")
    print(f"  {explanation.explanation[:100]}...")
```

### Convenience Functions

```python
# Single conflict analysis with default configuration
explanation = explain_single_conflict(belief1, belief2)

# Batch analysis with custom configuration
explanations = batch_explain_conflicts(belief_pairs, custom_config)
```

## Configuration

### Environment Variables

Currently, the explainer uses sensible defaults but can be configured programmatically. Future versions may support environment variable configuration.

### Configuration Dictionary

```python
config = {
    # Conflict detection thresholds
    "semantic_similarity_threshold": 0.7,   # Similarity threshold for analysis
    "hard_conflict_threshold": 0.8,         # Threshold for hard conflicts
    "soft_conflict_threshold": 0.6,         # Threshold for soft conflicts
    
    # Analysis parameters
    "max_keywords_extracted": 10,           # Maximum keywords to extract
    "min_keyword_relevance": 0.3,           # Minimum relevance for keywords
    "explanation_detail_level": "detailed", # "brief", "detailed", "comprehensive"
    
    # Resolution strategy preferences
    "prefer_merge_strategies": True,         # Prefer merging over replacement
    "suggest_human_review_threshold": 0.8,  # When to require human review
    "max_follow_up_questions": 5,           # Maximum questions to generate
}
```

## Conflict Types

The explainer identifies five primary conflict types:

### 1. Semantic Conflicts
Direct contradictions in meaning or content.

**Example:**
- Belief A: "AI is beneficial for humanity"
- Belief B: "AI is harmful to humanity"

**Characteristics:**
- Opposing semantic meanings
- Direct contradictions
- Often involves negation or antonyms

### 2. Temporal Conflicts
Conflicts in time-based claims or temporal scope.

**Example:**
- Belief A: "Machine learning was rule-based in the past"
- Belief B: "Machine learning is neural network-based now"

**Characteristics:**
- Different time periods
- Temporal qualifiers (past, present, future)
- Evolution of concepts over time

### 3. Scope Conflicts
Differences in applicability, universality, or scope.

**Example:**
- Belief A: "All AI systems require extensive testing"
- Belief B: "Some AI systems can be deployed with minimal testing"

**Characteristics:**
- Universal vs. particular claims
- Scope qualifiers (all, some, none, most)
- Domain or context specificity

### 4. Definitional Conflicts
Different definitions or interpretations of the same concept.

**Example:**
- Belief A: "Intelligence requires consciousness"
- Belief B: "Intelligence is pattern recognition and problem-solving"

**Characteristics:**
- High semantic similarity but different meanings
- Different conceptual frameworks
- Definitional ambiguity

### 5. Value Conflicts
Conflicting value judgments or moral positions.

**Example:**
- Belief A: "Privacy is more important than security"
- Belief B: "Security should be prioritized over privacy"

**Characteristics:**
- Moral or ethical judgments
- Value-laden language
- Competing priorities or principles

## Conflict Severity Levels

### Soft Conflicts
Minor contradictions that may be easily resolved.

**Characteristics:**
- Low NLI conflict confidence (< 0.6)
- Potential for reconciliation through clarification
- May be due to context or scope differences

**Resolution Strategies:**
- Context specification
- Belief merging
- Scope clarification

### Medium Conflicts
Moderate contradictions requiring careful analysis.

**Characteristics:**
- Medium NLI conflict confidence (0.6-0.8)
- Clear contradictions but potential for resolution
- May require evidence evaluation

**Resolution Strategies:**
- Evidence comparison
- Confidence adjustment
- Conditional belief formation

### Hard Conflicts
Strong contradictions requiring significant resolution effort.

**Characteristics:**
- High NLI conflict confidence (> 0.8)
- Fundamental disagreements
- Often involves protected beliefs

**Resolution Strategies:**
- Human expert review
- Belief suspension
- Escalation to decision-makers

## Analysis Process

### Step-by-Step Conflict Analysis

1. **NLI Conflict Analysis**: Uses natural language inference to detect semantic conflicts
2. **Semantic Similarity**: Calculates embedding-based similarity scores
3. **Keyword Extraction**: Identifies conflicting terms and concepts
4. **Conflict Classification**: Determines conflict type and severity
5. **Explanation Generation**: Creates natural language explanation
6. **Reframing Suggestions**: Proposes ways to reframe the conflict
7. **Question Generation**: Creates follow-up questions for clarification
8. **Resolution Strategies**: Suggests specific resolution approaches
9. **Human Input Assessment**: Determines if human review is required

### Pattern Recognition

The explainer uses regex patterns to identify different conflict types:

```python
conflict_patterns = {
    "negation": [
        r"\b(not|never|no|cannot|can't|won't|shouldn't|couldn't)\b",
        r"\b(isn't|aren't|wasn't|weren't|haven't|hasn't|hadn't)\b"
    ],
    "temporal": [
        r"\b(always|never|sometimes|often|rarely|occasionally)\b",
        r"\b(past|present|future|now|then|before|after|during)\b"
    ],
    "scope": [
        r"\b(all|some|none|most|few|many|several|every|any)\b",
        r"\b(only|just|merely|exclusively|primarily|mainly)\b"
    ],
    "value": [
        r"\b(good|bad|positive|negative|beneficial|harmful)\b",
        r"\b(should|shouldn't|must|must not|ought|ought not)\b"
    ]
}
```

## Integration Points

### NLI Conflict Checker Integration

```python
from nli_conflict_checker import nli_check

# The explainer automatically uses the existing NLI system
explanation = explainer.explain_conflict(belief1, belief2)

# NLI results are included in the explanation
if explanation.nli_conflict_score is not None:
    print(f"NLI Confidence: {explanation.nli_conflict_score:.3f}")
```

### Belief Registry Integration

```python
from belief_registry import BeliefRegistry
from contradiction_explainer import ContradictionExplainer

registry = BeliefRegistry()
explainer = ContradictionExplainer()

# Find conflicting beliefs in registry
conflicts = registry.detect_conflicts()

# Explain each conflict
for conflict in conflicts:
    belief1 = registry.get_belief(conflict.belief_a)
    belief2 = registry.get_belief(conflict.belief_b)
    explanation = explainer.explain_conflict(belief1, belief2)
    
    # Log detailed explanation
    print(f"Conflict between {conflict.belief_a} and {conflict.belief_b}:")
    print(f"  Type: {explanation.conflict_type}")
    print(f"  Explanation: {explanation.explanation}")
```

### Journal Engine Integration

```python
from journal_engine import generate_journal_entry

def log_conflict_analysis(belief1, belief2, explanation):
    """Log conflict analysis to journal"""
    
    generate_journal_entry(
        content=f"Analyzed conflict between beliefs {belief1.id} and {belief2.id}. "
                f"Type: {explanation.conflict_type}, Severity: {explanation.severity}. "
                f"{explanation.explanation}",
        tags=["conflict_analysis", explanation.conflict_type, explanation.severity],
        source="contradiction_explainer",
        metadata={
            "belief1_id": str(belief1.id),
            "belief2_id": str(belief2.id),
            "conflict_type": explanation.conflict_type,
            "severity": explanation.severity,
            "confidence": explanation.confidence,
            "requires_human_input": explanation.requires_human_input
        }
    )
```

## Usage Examples

### Basic Conflict Analysis

```python
from contradiction_explainer import ContradictionExplainer
from belief_models import Belief
from datetime import datetime, timezone

# Create explainer
explainer = ContradictionExplainer()

# Create conflicting beliefs
belief_a = Belief(
    statement="Transparency is always essential for trustworthy AI",
    belief_type="normative",
    created_at=datetime.now(timezone.utc),
    provenance="user",
    confidence=0.9,
    tags={"transparency", "trust", "ethics"}
)

belief_b = Belief(
    statement="Sometimes AI systems must operate without full transparency for security",
    belief_type="normative",
    created_at=datetime.now(timezone.utc),
    provenance="security_expert",
    confidence=0.8,
    tags={"security", "operational", "pragmatic"}
)

# Analyze conflict
explanation = explainer.explain_conflict(belief_a, belief_b)

print(f"""
Conflict Analysis:
Type: {explanation.conflict_type}
Severity: {explanation.severity}
Confidence: {explanation.confidence:.3f}

Explanation:
{explanation.explanation}

Conflicting Keywords:
{', '.join(explanation.keywords_in_conflict)}

Suggested Reframe:
{explanation.suggested_reframe}

Follow-up Questions:
""")

for i, question in enumerate(explanation.follow_up_questions, 1):
    print(f"{i}. {question}")

print(f"""
Resolution Strategies:
""")

for i, strategy in enumerate(explanation.resolution_strategies, 1):
    print(f"{i}. {strategy}")

print(f"Requires Human Input: {explanation.requires_human_input}")
```

### Temporal Conflict Analysis

```python
# Beliefs about AI development over time
historical_belief = Belief(
    statement="AI research focused primarily on symbolic reasoning in the 1980s",
    belief_type="descriptive",
    created_at=datetime.now(timezone.utc) - timedelta(days=30),
    provenance="historical_analysis",
    confidence=0.9,
    tags={"history", "symbolic_ai", "1980s"}
)

current_belief = Belief(
    statement="AI research now focuses primarily on machine learning and neural networks",
    belief_type="descriptive", 
    created_at=datetime.now(timezone.utc),
    provenance="current_research",
    confidence=0.95,
    tags={"current", "machine_learning", "neural_networks"}
)

explanation = explainer.explain_conflict(historical_belief, current_belief)

# This should be identified as a temporal conflict, not a contradiction
print(f"Conflict Type: {explanation.conflict_type}")  # Should be "temporal"
print(f"Severity: {explanation.severity}")  # Should be "soft" or "medium"
print(f"Suggested Reframe: {explanation.suggested_reframe}")
```

### Batch Analysis with Filtering

```python
from contradiction_explainer import batch_explain_conflicts

# Process multiple conflicts
belief_pairs = [
    (belief_always_safe, belief_sometimes_unsafe),
    (belief_privacy_first, belief_security_first),
    (belief_human_control, belief_ai_autonomy),
    (belief_open_source, belief_proprietary)
]

explanations = batch_explain_conflicts(belief_pairs)

# Filter by severity
hard_conflicts = [e for e in explanations if e.severity == "hard"]
requires_human = [e for e in explanations if e.requires_human_input]

print(f"Total conflicts analyzed: {len(explanations)}")
print(f"Hard conflicts requiring attention: {len(hard_conflicts)}")
print(f"Conflicts requiring human input: {len(requires_human)}")

# Analyze conflict types
conflict_types = {}
for explanation in explanations:
    conflict_types[explanation.conflict_type] = conflict_types.get(explanation.conflict_type, 0) + 1

print("\nConflict Type Distribution:")
for conflict_type, count in conflict_types.items():
    print(f"  {conflict_type}: {count}")
```

### Custom Configuration for Specific Domains

```python
# Configuration for ethical AI analysis
ethics_config = {
    "semantic_similarity_threshold": 0.6,  # Lower threshold for nuanced ethics
    "hard_conflict_threshold": 0.7,        # Ethics conflicts are often hard
    "explanation_detail_level": "comprehensive",
    "prefer_merge_strategies": False,      # Ethics often requires choosing
    "max_follow_up_questions": 7,          # More questions for complex issues
}

ethics_explainer = ContradictionExplainer(ethics_config)

# Analyze ethical conflicts with specialized configuration
ethical_explanation = ethics_explainer.explain_conflict(
    belief_utilitarian, belief_deontological
)
```

## Advanced Features

### Metadata-Informed Analysis

The explainer considers belief metadata for enhanced analysis:

```python
def analyze_metadata_influence(explanation):
    """Analyze how belief metadata influences conflict analysis"""
    
    metadata = explanation.belief_metadata_diff
    
    print(f"Metadata Analysis:")
    print(f"  Confidence difference: {metadata['confidence_delta']:.3f}")
    print(f"  Importance difference: {metadata['importance_delta']:.3f}")
    print(f"  Age difference: {metadata['age_delta_days']:.1f} days")
    print(f"  Different sources: {metadata['different_sources']}")
    print(f"  Protection conflict: {metadata['protection_conflict']}")
    
    # Metadata can influence resolution strategies
    if metadata['different_sources']:
        print("  → Source credibility analysis recommended")
    
    if metadata['age_delta_days'] > 30:
        print("  → Temporal validity check recommended")
    
    if metadata['confidence_delta'] > 0.3:
        print("  → Confidence reassessment recommended")
```

### Semantic Similarity Analysis

```python
def analyze_semantic_relationship(explanation):
    """Analyze the semantic relationship between conflicting beliefs"""
    
    similarity = explanation.semantic_similarity
    
    if similarity > 0.8:
        print("High semantic similarity - likely definitional conflict")
        print("Consider clarifying key terms and concepts")
    elif similarity > 0.5:
        print("Moderate semantic similarity - related concepts in conflict")
        print("Look for scope or context differences")
    else:
        print("Low semantic similarity - may be unrelated or scope issue")
        print("Verify that these beliefs actually conflict")
```

### Resolution Strategy Selection

```python
def prioritize_resolution_strategies(explanation):
    """Prioritize resolution strategies based on conflict characteristics"""
    
    strategies = explanation.resolution_strategies
    
    # Prioritize based on conflict type and severity
    priority_strategies = []
    
    if explanation.conflict_type == "temporal":
        priority_strategies.extend([s for s in strategies if "temporal" in s.lower()])
    
    if explanation.severity == "hard":
        priority_strategies.extend([s for s in strategies if "human" in s.lower()])
    
    if explanation.confidence > 0.8:
        priority_strategies.extend([s for s in strategies if "evidence" in s.lower()])
    
    # Remove duplicates while preserving order
    seen = set()
    unique_priorities = []
    for strategy in priority_strategies:
        if strategy not in seen:
            unique_priorities.append(strategy)
            seen.add(strategy)
    
    return unique_priorities
```

## Performance Considerations

### Optimization for Large-Scale Analysis

```python
# For large numbers of belief pairs
def efficient_conflict_analysis(belief_pairs, batch_size=50):
    """Process conflicts in batches for memory efficiency"""
    
    all_explanations = []
    
    for i in range(0, len(belief_pairs), batch_size):
        batch = belief_pairs[i:i + batch_size]
        
        print(f"Processing batch {i//batch_size + 1}/{(len(belief_pairs)-1)//batch_size + 1}")
        
        batch_explanations = batch_explain_conflicts(batch)
        all_explanations.extend(batch_explanations)
        
        # Optional: persist intermediate results
        # save_explanations(batch_explanations, f"batch_{i//batch_size}")
    
    return all_explanations
```

### Memory Usage

Approximate memory usage per conflict analysis:
- With embeddings: ~5KB per conflict pair
- Without embeddings: ~2KB per conflict pair

### Processing Speed

Typical processing speeds:
- Single conflict: ~50-200ms
- Batch of 10 conflicts: ~300ms-1s
- Batch of 100 conflicts: ~2-8s

## Error Handling

### Graceful Degradation

```python
# The explainer handles various error conditions gracefully

# Missing or invalid belief content
empty_belief = Belief(statement="", ...)
explanation = explainer.explain_conflict(empty_belief, normal_belief)
# Returns valid explanation with appropriate warnings

# NLI service unavailable
with patch('nli_conflict_checker.nli_check', side_effect=Exception("Service down")):
    explanation = explainer.explain_conflict(belief1, belief2)
    # Still provides analysis using heuristic methods

# Embedding model unavailable
with patch.object(explainer, 'embeddings_available', False):
    explanation = explainer.explain_conflict(belief1, belief2)
    # Falls back to keyword-based similarity
```

### Error Recovery Strategies

| Error Type | Recovery Strategy |
|------------|------------------|
| NLI service failure | Use pattern-based analysis |
| Embedding model unavailable | Use keyword-based similarity |
| Missing belief metadata | Use default values with warnings |
| Invalid belief content | Generate basic explanation with low confidence |
| Network timeouts | Retry with exponential backoff |

## Testing

### Comprehensive Test Coverage

```bash
# Run all tests
python -m pytest test_contradiction_explainer.py -v

# Run specific test categories
python -m pytest test_contradiction_explainer.py::TestConflictExplanation -v
python -m pytest test_contradiction_explainer.py::TestContradictionExplainer -v
python -m pytest test_contradiction_explainer.py::TestNLIIntegration -v
python -m pytest test_contradiction_explainer.py::TestEdgeCasesAndErrorHandling -v
```

### Test Categories

- **20+ test cases** covering all conflict types
- **Edge cases**: Empty statements, identical beliefs, missing metadata
- **Error handling**: NLI failures, embedding unavailability
- **Integration**: NLI conflict checker, belief registry
- **Performance**: Batch processing, large datasets

## Monitoring and Debugging

### Analysis Quality Metrics

```python
def analyze_explanation_quality(explanations):
    """Analyze the quality of conflict explanations"""
    
    confidences = [e.confidence for e in explanations]
    
    print(f"Explanation Quality Metrics:")
    print(f"  Average confidence: {np.mean(confidences):.3f}")
    print(f"  Low confidence explanations (<0.5): {sum(1 for c in confidences if c < 0.5)}")
    print(f"  High confidence explanations (>0.8): {sum(1 for c in confidences if c > 0.8)}")
    
    # Analyze by conflict type
    by_type = {}
    for explanation in explanations:
        conflict_type = explanation.conflict_type
        if conflict_type not in by_type:
            by_type[conflict_type] = []
        by_type[conflict_type].append(explanation.confidence)
    
    print(f"\nConfidence by Conflict Type:")
    for conflict_type, confidences in by_type.items():
        print(f"  {conflict_type}: {np.mean(confidences):.3f} (n={len(confidences)})")
```

### Debug Mode

```python
# Enable detailed logging for debugging
import logging
logging.getLogger("contradiction_explainer").setLevel(logging.DEBUG)

# Analyze with debug output
explanation = explainer.explain_conflict(belief1, belief2)
```

## Future Enhancements

### Planned Features

1. **Multi-language support**: Analyze conflicts in multiple languages
2. **Contextual understanding**: Consider broader belief context
3. **Confidence calibration**: Improve explanation confidence accuracy
4. **Learning from resolutions**: Adapt based on successful conflict resolutions
5. **Visual conflict mapping**: Generate visual representations of conflicts

### Extensibility

```python
class CustomContradictionExplainer(ContradictionExplainer):
    """Extended explainer with domain-specific features"""
    
    def _analyze_domain_specific_conflict(self, belief1, belief2):
        """Add domain-specific conflict analysis"""
        # Custom analysis logic here
        return domain_analysis
    
    def explain_conflict(self, belief1, belief2):
        # Get base explanation
        base_explanation = super().explain_conflict(belief1, belief2)
        
        # Add domain-specific analysis
        domain_analysis = self._analyze_domain_specific_conflict(belief1, belief2)
        
        # Enhance explanation
        enhanced_explanation = ConflictExplanation(
            explanation=f"{base_explanation.explanation} {domain_analysis.insight}",
            # ... other enhanced fields
        )
        
        return enhanced_explanation
```

## Troubleshooting

### Common Issues

**Poor conflict detection**
- Check NLI service availability
- Verify embedding model loading
- Review conflict type patterns

**Inconsistent explanations**
- Ensure belief metadata is complete
- Check for timezone issues
- Verify configuration consistency

**Performance issues**
- Use batch processing for multiple conflicts
- Consider reducing explanation detail level
- Check memory usage with large datasets

### Debug Information

```python
# Detailed analysis breakdown
explanation = explainer.explain_conflict(belief1, belief2)

print(f"Debug Information:")
print(f"  Semantic similarity: {explanation.semantic_similarity:.3f}")
print(f"  NLI conflict score: {explanation.nli_conflict_score}")
print(f"  Keywords extracted: {len(explanation.keywords_in_conflict)}")
print(f"  Resolution strategies: {len(explanation.resolution_strategies)}")
print(f"  Explanation confidence: {explanation.confidence:.3f}")
```

## Conclusion

The Contradiction Explainer provides sophisticated conflict analysis capabilities for Axiom's belief system. Its multi-dimensional approach to conflict detection, natural language explanations, and integration with existing systems make it a powerful tool for maintaining belief consistency and supporting human decision-making.

The system's robustness, extensibility, and comprehensive error handling ensure reliable operation in production environments while providing actionable insights for belief conflict resolution.

For additional support or feature requests, consult the test suite and integration examples, or refer to the Axiom development team.