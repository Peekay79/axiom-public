# Belief Influence Mapper Documentation

## Overview

The **Belief Influence Mapper** is a core component of the Axiom Cognitive Architecture that scores and traces the influence radius of beliefs across the entire cognitive system. It analyzes how individual beliefs impact goal inference, planning memory, emotional states, decision outcomes, and other cognitive processes.

### Key Features

- **Comprehensive Influence Analysis**: Analyzes belief influence across goals, plans, actions, emotions, memories, and contradictions
- **Sophisticated Scoring Algorithm**: Multi-factor scoring considering depth, emotional modulation, frequency, trust, and temporal factors
- **Real-time Visualization**: Tree graphs, influence matrices, and network visualizations
- **High-influence Belief Detection**: Automatic scanning and prioritization of influential beliefs
- **Emotional Context Integration**: Dynamic influence amplification based on emotional states
- **Cross-system Integration**: Seamless integration with all Axiom cognitive components
- **Caching and Performance**: Optimized analysis with intelligent caching mechanisms

## Architecture

### Core Components

```
BeliefInfluenceMapper
├── Core Analysis Engine
│   ├── Goal Influence Analysis
│   ├── Planning Influence Analysis
│   ├── Action Influence Analysis
│   ├── Emotional Influence Analysis
│   ├── Memory Influence Analysis
│   └── Contradiction Influence Analysis
├── Scoring Algorithms
│   ├── Multi-factor Scoring
│   ├── Emotional Amplification
│   ├── Temporal Decay
│   └── Influence Type Detection
├── Visualization Interface
│   ├── Tree Graph Generation
│   ├── Influence Matrix Display
│   └── Network Visualization
└── Integration Layer
    ├── Belief Registry Integration
    ├── Goal Drive Engine Integration
    ├── Planning Memory Integration
    ├── Emotional Model Integration
    └── Contradiction System Integration
```

### Data Models

#### InfluenceTarget
Represents an entity influenced by a belief:
```python
@dataclass
class InfluenceTarget:
    target_id: UUID
    target_type: str  # "goal", "action", "emotion", "memory", "contradiction"
    influence_score: float  # 0.0-1.0
    influence_type: InfluenceType
    influence_path: List[str]  # Path of influence propagation
    confidence: float = 0.8
    metadata: Dict[str, Any] = field(default_factory=dict)
```

#### BeliefInfluenceReport
Comprehensive report of a belief's influence:
```python
@dataclass
class BeliefInfluenceReport:
    belief_id: UUID
    belief_statement: str
    total_influence_score: float  # 0.0-1.0 normalized
    influence_level: InfluenceLevel
    influence_breakdown: Dict[str, float]  # area -> score
    downstream_entities: List[InfluenceTarget]
    influence_types: List[InfluenceType]
    suggested_actions: List[str]
    requires_attention: bool
    protection_recommended: bool
    # Additional metadata...
```

### Influence Types

The system recognizes eight distinct types of belief influence:

1. **MOTIVATIONAL**: Influences goals and drives
2. **EMOTIONAL**: Affects emotional states and responses
3. **DEFINITIONAL**: Shapes understanding and concepts
4. **CAUSAL**: Influences causal reasoning and predictions
5. **BEHAVIORAL**: Affects actions and decisions
6. **EPISTEMIC**: Influences knowledge and learning
7. **VALUE_BASED**: Shapes values and preferences
8. **TEMPORAL**: Time-related influence patterns

### Influence Levels

Beliefs are categorized into five influence levels:

- **CRITICAL** (0.8-1.0): Beliefs with system-wide impact requiring protection
- **HIGH** (0.6-0.8): Highly influential beliefs requiring attention
- **MODERATE** (0.4-0.6): Moderately influential beliefs
- **LOW** (0.2-0.4): Low influence beliefs
- **MINIMAL** (0.0-0.2): Minimal influence beliefs

## API Reference

### BeliefInfluenceMapper Class

#### Initialization

```python
from belief_influence_mapper import BeliefInfluenceMapper

# Basic initialization
mapper = BeliefInfluenceMapper()

# With custom configuration
config = {
    'max_depth': 10,
    'min_threshold': 0.1,
    'temporal_decay': 0.9,
    'cache_ttl_seconds': 600
}
mapper = BeliefInfluenceMapper(config)
```

#### Core Methods

##### analyze_belief_influence()

Analyzes the influence of a specific belief across the cognitive system.

```python
async def analyze_belief_influence(
    self,
    belief_id: UUID,
    scope_filter: Optional[List[str]] = None,
    depth: Optional[int] = None,
    emotional_context: Optional[EmotionalStateSnapshot] = None
) -> BeliefInfluenceReport
```

**Parameters:**
- `belief_id`: UUID of the belief to analyze
- `scope_filter`: Optional list of scopes ("goals", "plans", "actions", "emotions", "memories", "contradictions")
- `depth`: Maximum depth of influence analysis (default: 5)
- `emotional_context`: Current emotional state for influence modulation

**Returns:** BeliefInfluenceReport with comprehensive analysis

**Example:**
```python
import asyncio
from uuid import UUID
from belief_resolution_engine import EmotionalStateSnapshot

async def analyze_belief():
    mapper = BeliefInfluenceMapper()
    
    # Basic analysis
    belief_id = UUID("your-belief-id-here")
    report = await mapper.analyze_belief_influence(belief_id)
    
    # With emotional context
    emotional_context = EmotionalStateSnapshot(
        primary_emotion="concerned",
        intensity=0.7,
        confidence=0.8,
        emotional_stability=0.6
    )
    
    report = await mapper.analyze_belief_influence(
        belief_id,
        scope_filter=["goals", "emotions"],
        emotional_context=emotional_context
    )
    
    print(f"Total influence score: {report.total_influence_score:.3f}")
    print(f"Influence level: {report.influence_level.value}")
    print(f"Requires attention: {report.requires_attention}")

asyncio.run(analyze_belief())
```

##### scan_high_influence_beliefs()

Scans all beliefs and returns the most influential ones.

```python
async def scan_high_influence_beliefs(
    self,
    limit: int = 10,
    scope_filter: Optional[List[str]] = None,
    emotional_context: Optional[EmotionalStateSnapshot] = None
) -> List[BeliefInfluenceReport]
```

**Example:**
```python
async def find_influential_beliefs():
    mapper = BeliefInfluenceMapper()
    
    # Get top 10 most influential beliefs
    reports = await mapper.scan_high_influence_beliefs(limit=10)
    
    print("Top Influential Beliefs:")
    for i, report in enumerate(reports, 1):
        print(f"{i}. {report.belief_statement[:60]}...")
        print(f"   Score: {report.total_influence_score:.3f}")
        print(f"   Level: {report.influence_level.value}")
        print()

asyncio.run(find_influential_beliefs())
```

##### track_influence_volatility()

Tracks how a belief's influence changes over time.

```python
async def track_influence_volatility(
    self,
    belief_id: UUID,
    time_window_hours: int = 168  # 1 week
) -> Dict[str, Any]
```

**Example:**
```python
async def track_volatility():
    mapper = BeliefInfluenceMapper()
    belief_id = UUID("your-belief-id-here")
    
    volatility_data = await mapper.track_influence_volatility(
        belief_id,
        time_window_hours=168  # 1 week
    )
    
    print(f"Volatility score: {volatility_data['volatility_score']}")
    print(f"Trend: {volatility_data['trend']}")

asyncio.run(track_volatility())
```

##### pin_belief()

Pins a high-influence belief to prevent accidental modification.

```python
def pin_belief(self, belief_id: UUID, reason: str = "High influence") -> bool
```

**Example:**
```python
mapper = BeliefInfluenceMapper()
belief_id = UUID("your-critical-belief-id")

success = mapper.pin_belief(belief_id, "Critical safety belief")
if success:
    print("Belief successfully pinned for protection")
```

## Usage Examples

### Basic Belief Analysis

```python
import asyncio
from belief_influence_mapper import BeliefInfluenceMapper
from uuid import UUID

async def basic_analysis_example():
    """Basic belief influence analysis"""
    mapper = BeliefInfluenceMapper()
    
    # Analyze a specific belief
    belief_id = UUID("your-belief-uuid-here")
    report = await mapper.analyze_belief_influence(belief_id)
    
    # Display results
    print(f"Belief: {report.belief_statement}")
    print(f"Total Influence Score: {report.total_influence_score:.3f}")
    print(f"Influence Level: {report.influence_level.value}")
    
    # Show breakdown by area
    print("\nInfluence Breakdown:")
    for area, score in report.influence_breakdown.items():
        print(f"  {area}: {score:.3f}")
    
    # Show top influenced entities
    print(f"\nTop Influenced Entities:")
    for target in report.downstream_entities[:5]:
        print(f"  {target.target_type}: {target.influence_score:.3f}")

asyncio.run(basic_analysis_example())
```

### Emotional Context Analysis

```python
async def emotional_context_example():
    """Analyze belief influence with emotional context"""
    mapper = BeliefInfluenceMapper()
    
    # Create emotional context
    from belief_resolution_engine import EmotionalStateSnapshot
    
    emotional_context = EmotionalStateSnapshot(
        primary_emotion="anxious",
        intensity=0.8,
        confidence=0.7,
        emotional_stability=0.4,
        stress_level=0.7
    )
    
    belief_id = UUID("your-belief-uuid-here")
    
    # Analyze with emotional context
    report = await mapper.analyze_belief_influence(
        belief_id,
        emotional_context=emotional_context
    )
    
    print(f"Emotional Amplification: {report.emotional_amplification:.2f}")
    print(f"Base vs Amplified Score:")
    print(f"  Total Score: {report.total_influence_score:.3f}")
    
    # Compare with neutral analysis
    neutral_report = await mapper.analyze_belief_influence(belief_id)
    print(f"  Neutral Score: {neutral_report.total_influence_score:.3f}")

asyncio.run(emotional_context_example())
```

### High-Influence Belief Scanning

```python
async def scanning_example():
    """Scan for high-influence beliefs"""
    mapper = BeliefInfluenceMapper()
    
    # Scan for top influential beliefs
    reports = await mapper.scan_high_influence_beliefs(
        limit=15,
        scope_filter=["goals", "emotions", "actions"]
    )
    
    print("High-Influence Beliefs Report")
    print("=" * 50)
    
    for i, report in enumerate(reports, 1):
        print(f"{i:2d}. {report.belief_statement[:50]:<50}")
        print(f"    Score: {report.total_influence_score:.3f} | "
              f"Level: {report.influence_level.value:8} | "
              f"Targets: {len(report.downstream_entities):2d}")
        
        if report.requires_attention:
            print(f"    ⚠️  Requires Attention")
        if report.protection_recommended:
            print(f"    🛡️  Protection Recommended")
        print()

asyncio.run(scanning_example())
```

### Scope-Filtered Analysis

```python
async def scope_filtering_example():
    """Analyze belief influence with specific scope filters"""
    mapper = BeliefInfluenceMapper()
    belief_id = UUID("your-belief-uuid-here")
    
    # Analyze different scopes
    scopes = {
        "Goals & Actions": ["goals", "actions"],
        "Emotions & Memory": ["emotions", "memories"],
        "Planning & Contradictions": ["plans", "contradictions"]
    }
    
    for scope_name, scope_filter in scopes.items():
        report = await mapper.analyze_belief_influence(
            belief_id,
            scope_filter=scope_filter
        )
        
        print(f"{scope_name} Analysis:")
        print(f"  Total Score: {report.total_influence_score:.3f}")
        print(f"  Breakdown: {report.influence_breakdown}")
        print(f"  Target Count: {len(report.downstream_entities)}")
        print()

asyncio.run(scope_filtering_example())
```

## Visualization Interface

The Belief Influence Mapper includes a comprehensive visualization interface accessible through the `demo_belief_influence.py` module.

### Interactive CLI Explorer

Start the interactive explorer:

```bash
python audits/demo_belief_influence.py interactive
```

Available commands:
- `analyze <belief_id>` - Analyze specific belief by UUID
- `search <text>` - Search and analyze beliefs containing text
- `scan [limit]` - Scan top N most influential beliefs
- `emotional <emotion>` - Set emotional context (anxious, excited, calm, etc.)
- `scope <areas>` - Set analysis scope (goals,plans,emotions)
- `matrix` - Show global influence matrix
- `help` - Show available commands
- `quit` - Exit explorer

### Command Line Usage

```bash
# Scan top 10 influential beliefs
python audits/demo_belief_influence.py scan 10

# Analyze specific belief
python audits/demo_belief_influence.py analyze <belief-uuid>

# Analyze by searching for text
python audits/demo_belief_influence.py analyze "AI safety"
```

### Programmatic Visualization

```python
from audits.demo_belief_influence import BeliefInfluenceVisualizer
import asyncio

async def visualization_example():
    visualizer = BeliefInfluenceVisualizer()
    
    # Run comprehensive demonstration
    result = await visualizer.demonstrate_belief_influence(
        belief_statement="AI safety is important",
        scope_filter=["goals", "emotions"],
        emotional_context={"emotion": "concerned", "intensity": 0.7}
    )
    
    # Access visualization data
    if "visualizations" in result:
        for viz_type, path in result["visualizations"].items():
            print(f"{viz_type}: {path}")

asyncio.run(visualization_example())
```

## Implementation Details

### Influence Scoring Algorithm

The influence scoring algorithm uses a sophisticated multi-factor approach:

#### Base Score Calculation
```python
base_score = (belief.confidence * belief.importance * target.confidence) ** 0.5
```

#### State and Context Modifiers
- **Goal State Multipliers**: Active goals receive higher scores than dormant ones
- **Drive Strength Boost**: Current motivational pressure amplifies influence
- **Emotional Amplification**: Emotional context modulates all scores
- **Temporal Decay**: Recent beliefs and targets receive higher scores
- **Category-Specific Boosts**: Domain expertise and relevance modifiers

#### Final Score Computation
```python
final_score = (
    base_score * 
    state_multiplier * 
    (1 + drive_boost) * 
    emotional_multiplier * 
    temporal_factor * 
    (1 + category_boost)
)
```

### Emotional Amplification

Emotional context significantly modulates influence scores:

```python
def calculate_emotional_amplification(emotional_context):
    # Base amplification from intensity
    base_amp = 1.0 + (intensity - 0.5) * 0.5
    
    # Emotion-specific adjustments
    emotion_multipliers = {
        "anxious": 1.2,
        "excited": 1.3,
        "frustrated": 1.1,
        "curious": 1.2,
        "confident": 1.1,
        "uncertain": 0.9,
        "calm": 0.95
    }
    
    # Stability factor
    stability_factor = 0.5 + emotional_stability * 0.5
    
    return base_amp * emotion_multiplier * stability_factor
```

### Temporal Decay

Recent beliefs and targets receive higher influence scores:

```python
def calculate_temporal_decay(timestamp):
    days_ago = (now - timestamp).total_seconds() / 86400
    decay_factor = TEMPORAL_DECAY_FACTOR ** days_ago
    return max(decay_factor, 0.1)  # Minimum threshold
```

### Cross-System Integration

The mapper integrates with multiple Axiom components:

- **Belief Registry**: Source belief data and metadata
- **Goal Drive Engine**: Goal inference and action recommendations
- **Planning Memory**: Active goals, planned actions, and historical data
- **Emotional Model**: Current emotional state and stability
- **Contradiction Explainer**: Conflict detection and pressure analysis
- **Journal Engine**: Historical reinforcement patterns

## Configuration

### Mapper Configuration

```python
config = {
    # Analysis depth and thresholds
    'max_depth': 5,                    # Maximum analysis depth
    'min_threshold': 0.05,             # Minimum influence threshold
    'temporal_decay': 0.95,            # Daily temporal decay factor
    
    # Performance settings
    'cache_ttl_seconds': 300,          # Cache time-to-live (5 minutes)
    
    # Scoring parameters
    'high_influence_threshold': 0.7,   # Threshold for high influence
    'emotional_amplification_factor': 1.5,  # Maximum emotional amplification
    
    # Integration settings
    'max_active_goals': 12,            # Maximum goals to consider
    'max_graph_nodes': 100,            # Maximum network nodes
}

mapper = BeliefInfluenceMapper(config)
```

### Visualization Configuration

```python
# Visualization color scheme
node_colors = {
    InfluenceType.MOTIVATIONAL: '#FF6B6B',     # Red
    InfluenceType.EMOTIONAL: '#4ECDC4',        # Teal
    InfluenceType.DEFINITIONAL: '#45B7D1',     # Blue
    InfluenceType.CAUSAL: '#96CEB4',           # Green
    InfluenceType.BEHAVIORAL: '#FECA57',       # Yellow
    InfluenceType.EPISTEMIC: '#9B59B6',        # Purple
    InfluenceType.VALUE_BASED: '#E55039',      # Dark Red
    InfluenceType.TEMPORAL: '#78E08F'          # Light Green
}

# Size mapping for influence levels
influence_level_sizes = {
    InfluenceLevel.MINIMAL: 200,
    InfluenceLevel.LOW: 400,
    InfluenceLevel.MODERATE: 600,
    InfluenceLevel.HIGH: 800,
    InfluenceLevel.CRITICAL: 1000
}
```

## Best Practices

### When to Use Belief Influence Analysis

1. **Before Belief Modification**: Analyze influence before updating high-confidence beliefs
2. **Goal System Changes**: When modifying goal hierarchies or priorities
3. **System Stability Monitoring**: Regular scanning for unstable influence patterns
4. **Contradiction Resolution**: Understanding belief conflicts and their system impact
5. **Decision Making**: Evaluating the cognitive impact of major decisions

### Performance Optimization

1. **Use Scope Filters**: Limit analysis to relevant cognitive areas
2. **Leverage Caching**: Allow cache to reduce redundant computations
3. **Batch Analysis**: Use scanning functions for multiple beliefs
4. **Depth Limiting**: Use appropriate analysis depth for your use case
5. **Threshold Tuning**: Adjust minimum thresholds to filter noise

### Emotional Context Guidelines

1. **Current State**: Use actual emotional state when available
2. **Scenario Testing**: Test beliefs under different emotional contexts
3. **Stability Consideration**: Account for emotional stability in critical analyses
4. **Amplification Awareness**: Understand that emotions can significantly modify scores

### Influence Interpretation

1. **Score Ranges**: 
   - 0.0-0.2: Background influence
   - 0.2-0.4: Notable influence
   - 0.4-0.6: Significant influence
   - 0.6-0.8: High influence (requires attention)
   - 0.8-1.0: Critical influence (requires protection)

2. **Type Significance**:
   - **VALUE_BASED**: Core philosophical/ethical beliefs
   - **MOTIVATIONAL**: Goal-driving beliefs
   - **EMOTIONAL**: Mood and state-affecting beliefs
   - **CAUSAL**: Reasoning and prediction beliefs

3. **Protection Decisions**:
   - Protect beliefs with influence > 0.7
   - Protect normative beliefs with importance > 0.8
   - Protect foundational beliefs with confidence > 0.9

## Testing

The Belief Influence Mapper includes a comprehensive test suite with 25+ test cases:

```bash
# Run all tests
python test_belief_influence_mapper.py

# Run specific test class
python -m unittest test_belief_influence_mapper.TestInfluenceScoringAlgorithms

# Run with verbose output
python test_belief_influence_mapper.py -v
```

### Test Categories

1. **Initialization Tests**: Mapper setup and configuration
2. **Data Model Tests**: InfluenceTarget and BeliefInfluenceReport validation
3. **Scoring Algorithm Tests**: Multi-factor scoring validation
4. **Analysis Method Tests**: Individual cognitive area analysis
5. **End-to-End Tests**: Complete workflow validation
6. **Integration Tests**: Cross-system communication
7. **Performance Tests**: Caching and optimization
8. **Edge Case Tests**: Error handling and boundary conditions

## Troubleshooting

### Common Issues

#### Low Influence Scores
- **Cause**: Beliefs with low confidence or importance
- **Solution**: Check belief metadata; consider if beliefs are properly weighted

#### Missing Targets
- **Cause**: Minimum threshold too high or disconnected beliefs
- **Solution**: Lower `min_threshold` or verify belief connections

#### Slow Performance
- **Cause**: Large analysis depth or disabled caching
- **Solution**: Reduce `max_depth`, enable caching, use scope filters

#### Unexpected Emotional Amplification
- **Cause**: High emotional intensity or instability
- **Solution**: Verify emotional context parameters; check stability scores

### Debug Mode

Enable detailed logging for troubleshooting:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

mapper = BeliefInfluenceMapper()
# Detailed logs will show analysis steps
```

### Cache Issues

Clear cache if experiencing stale results:

```python
mapper.clear_cache()
```

## Future Enhancements

### Planned Features

1. **Historical Influence Tracking**: Full volatility analysis with historical data
2. **Predictive Influence Modeling**: Forecast influence changes over time
3. **Influence Network Analysis**: Advanced graph algorithms for influence patterns
4. **Real-time Monitoring**: Continuous influence tracking with alerts
5. **Machine Learning Integration**: Learned influence patterns and predictions
6. **Distributed Analysis**: Support for large-scale belief systems

### Extension Points

The system is designed for extensibility:

1. **Custom Influence Types**: Add domain-specific influence types
2. **Alternative Scoring**: Implement custom scoring algorithms
3. **New Visualization**: Add custom visualization formats
4. **Integration Modules**: Connect to additional cognitive systems
5. **Export Formats**: Add new data export capabilities

## Conclusion

The Belief Influence Mapper provides comprehensive, real-time analysis of how beliefs impact the entire Axiom cognitive system. By understanding influence patterns, the system can make better decisions about belief modification, goal prioritization, and cognitive stability.

For additional support or feature requests, consult the Axiom development team or contribute to the project repository.