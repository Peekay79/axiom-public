# Belief Pressure Mapper Documentation

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Pressure Scoring Formula](#pressure-scoring-formula)
4. [Trend Calculation Method](#trend-calculation-method)
5. [Configuration Guide](#configuration-guide)
6. [API Reference](#api-reference)
7. [JSON Export Schema](#json-export-schema)
8. [Usage Examples](#usage-examples)
9. [Integration Guide](#integration-guide)
10. [Performance Considerations](#performance-considerations)
11. [Troubleshooting](#troubleshooting)

## Overview

The Belief Pressure Mapper is a comprehensive system for tracking and analyzing contradiction pressure within Axiom's belief graph. It provides real-time monitoring of belief conflicts, identifies unstable regions, and offers temporal trend analysis to understand how belief tension evolves over time.

### Key Features

- **Contradiction Heatmap Generation**: Visual and programmatic tracking of belief pressure scores
- **Cluster Analysis**: Groups beliefs by semantic similarity and causal linkage to identify volatile regions
- **Temporal Trend Analysis**: Monitors pressure evolution with rolling trend calculations
- **Natural Language Explanations**: Integrates with ContradictionExplainer for human-readable insights
- **Runtime Monitoring**: Optional continuous monitoring with event detection
- **Interactive API**: Rich set of methods for querying pressure data
- **JSON Export**: Complete pressure map export for frontend visualization

### Core Concepts

- **Pressure Score**: A normalized value (0.0-1.0) representing the contradiction pressure on a belief
- **Cluster Pressure**: Aggregated pressure analysis for semantically related beliefs
- **Pressure Trend**: Temporal analysis showing if pressure is escalating, resolving, or stable
- **Hotspot Beliefs**: Individual beliefs with pressure scores above the configured threshold
- **Volatile Clusters**: Belief clusters containing multiple hotspot beliefs

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    BeliefPressureMapper                     │
├─────────────────────────────────────────────────────────────┤
│  Core Components:                                           │
│  • Pressure Score Calculator                               │
│  • Heatmap Generator                                        │
│  • Cluster Analyzer (DBSCAN + Semantic Embeddings)         │
│  • Trend Analyzer (Linear Regression)                      │
│  • Natural Language Explainer Integration                  │
│  • Runtime Monitor (Optional Thread)                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  BeliefRegistry │ │ContradictionExp │ │  JournalEngine  │
│                 │ │     lainer      │ │                 │
│ • get_beliefs() │ │ • explain_      │ │ • log_events()  │
│ • get_contradi  │ │   conflict()    │ │                 │
│   ctions()      │ │                 │ │                 │
└─────────────────┘ └─────────────────┘ └─────────────────┘
                              │
                              ▼
              ┌─────────────────────────────────┐
              │       Data Persistence          │
              │                                 │
              │ • pressure_history.jsonl        │
              │ • Timestamped pressure logs     │
              │ • Automatic log rotation        │
              └─────────────────────────────────┘
```

### Data Flow

1. **Belief Collection**: Retrieves beliefs and contradictions from BeliefRegistry
2. **Pressure Calculation**: Computes weighted pressure scores for each belief
3. **Cluster Analysis**: Groups beliefs using semantic embeddings and DBSCAN
4. **Trend Analysis**: Analyzes historical pressure data for temporal patterns
5. **Explanation Generation**: Uses ContradictionExplainer for natural language insights
6. **Event Detection**: Monitors for threshold violations and escalating trends
7. **Data Export**: Serializes complete analysis results to JSON

## Pressure Scoring Formula

The pressure score for a belief is calculated using a multi-factor weighted formula:

### Base Formula

```
raw_score = confidence_weight × importance_weight × decay_weight × conflict_pressure
normalized_score = sigmoid(raw_score)
```

### Component Calculations

#### 1. Confidence Weight
```python
confidence_weight = belief.confidence  # Direct from belief metadata (0.0-1.0)
```

#### 2. Importance Weight
```python
importance_weight = belief.importance  # Direct from belief metadata (0.0-1.0)
```

#### 3. Decay Weight
```python
age_days = (current_time - belief.created_at).days
decay_weight = exp(-age_days / belief.decay_half_life_days)
```

#### 4. Conflict Pressure
```python
if conflict_count > 0:
    conflict_pressure = min(1.0, log(conflict_count + 1) / log(10))
else:
    conflict_pressure = 0.0
```

#### 5. Sigmoid Normalization
```python
normalized_score = 1 / (1 + exp(-5 * (raw_score - 0.5)))
```

### Pressure Score Interpretation

| Score Range | Interpretation | Action Required |
|-------------|----------------|-----------------|
| 0.0 - 0.3   | Low pressure   | Monitor only    |
| 0.3 - 0.6   | Medium pressure| Review conflicts|
| 0.6 - 0.9   | High pressure  | Active resolution needed |
| 0.9 - 1.0   | Critical pressure | Immediate attention |

### Example Calculation

For a belief with:
- confidence = 0.9
- importance = 0.8  
- age = 10 days
- decay_half_life = 30 days
- conflicts = 3

```python
decay_weight = exp(-10/30) ≈ 0.716
conflict_pressure = log(4) / log(10) ≈ 0.602
raw_score = 0.9 × 0.8 × 0.716 × 0.602 ≈ 0.310
normalized_score = 1 / (1 + exp(-5 × (0.310 - 0.5))) ≈ 0.238
```

## Trend Calculation Method

Temporal trend analysis uses linear regression over a configurable time window to detect pressure evolution patterns.

### Linear Regression Implementation

```python
# Simple linear regression for trend detection
n = len(scores)
sum_x = sum(range(n))
sum_y = sum(scores)
sum_xy = sum(i * score for i, score in enumerate(scores))
sum_x2 = sum(i * i for i in range(n))

slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
```

### Trend Classification

| Slope Range | Direction | Description |
|-------------|-----------|-------------|
| slope > escalation_threshold | Escalating | Pressure increasing over time |
| slope < -escalation_threshold | Resolving | Pressure decreasing over time |
| -escalation_threshold ≤ slope ≤ escalation_threshold | Stable | Pressure relatively constant |

### Default Configuration

- **Time Window**: 7 days
- **Escalation Threshold**: 0.1
- **Minimum Data Points**: 3
- **History Retention**: 10,000 entries

### Confidence Intervals

Trend confidence intervals are calculated using standard deviation:

```python
score_std = np.std(scores)
confidence_interval = (
    max(0.0, mean_score - score_std),
    min(1.0, mean_score + score_std)
)
```

## Configuration Guide

### Basic Configuration

```python
config = {
    'pressure_threshold': 0.6,        # Unstable belief threshold
    'escalation_threshold': 0.1,      # Trend escalation threshold  
    'history_log_path': 'data/pressure_history.jsonl',
    'monitoring_interval': 300        # Monitoring interval (seconds)
}

mapper = BeliefPressureMapper(config=config)
```

### Advanced Configuration

```python
config = {
    # Thresholds
    'pressure_threshold': 0.7,
    'escalation_threshold': 0.15,
    'human_review_threshold': 0.6,
    
    # File paths
    'history_log_path': '/var/log/axiom/pressure_history.jsonl',
    'cluster_cache_path': '/tmp/clusters.json',
    
    # Performance
    'max_history_entries': 15000,
    'embedding_batch_size': 100,
    'cluster_eps': 0.3,
    'cluster_min_samples': 2,
    
    # Monitoring
    'monitoring_interval': 180,        # 3 minutes
    'alert_on_critical': True,
    'log_all_events': True
}
```

### Runtime Thresholds

You can adjust thresholds at runtime:

```python
mapper.pressure_threshold = 0.8
mapper.escalation_threshold = 0.05
```

### Environment Variables

The system respects these environment variables:

- `BELIEF_PRESSURE_THRESHOLD`: Default pressure threshold
- `BELIEF_ESCALATION_THRESHOLD`: Default escalation threshold
- `PRESSURE_LOG_PATH`: Default history log path
- `MONITORING_INTERVAL`: Default monitoring interval

## API Reference

### Core Methods

#### `async generate_heatmap(beliefs: Optional[List[Belief]] = None) -> Dict[UUID, PressureScore]`

Generates a comprehensive pressure heatmap for beliefs.

**Parameters:**
- `beliefs`: Optional list of beliefs to analyze (defaults to all beliefs)

**Returns:**
- Dictionary mapping belief IDs to PressureScore objects

**Example:**
```python
heatmap = await mapper.generate_heatmap()
for belief_id, score in heatmap.items():
    if score.score > 0.7:
        print(f"High pressure: {score.score:.3f}")
```

#### `async perform_cluster_analysis(beliefs: Optional[List[Belief]] = None) -> List[ClusterPressure]`

Groups beliefs and analyzes cluster-level pressure patterns.

**Parameters:**
- `beliefs`: Optional list of beliefs to cluster

**Returns:**
- List of ClusterPressure objects sorted by average pressure

**Example:**
```python
clusters = await mapper.perform_cluster_analysis()
for cluster in clusters:
    print(f"Cluster {cluster.cluster_id}: {cluster.average_pressure:.3f} avg pressure")
```

#### `async analyze_pressure_trends(time_window_days: int = 7) -> List[PressureTrend]`

Analyzes temporal pressure trends over specified time window.

**Parameters:**
- `time_window_days`: Number of days to analyze for trends

**Returns:**
- List of PressureTrend objects sorted by slope magnitude

**Example:**
```python
trends = await mapper.analyze_pressure_trends(14)
escalating = [t for t in trends if t.trend_direction == "escalating"]
```

### Interactive API Methods

#### `async get_high_pressure_beliefs(top_n: int = 10) -> List[Tuple[Belief, PressureScore]]`

Retrieves beliefs with highest pressure scores.

**Example:**
```python
high_pressure = await mapper.get_high_pressure_beliefs(5)
for belief, score in high_pressure:
    print(f"{belief.statement}: {score.score:.3f}")
```

#### `async get_cluster_pressure_summary() -> Dict[str, Any]`

Returns comprehensive cluster analysis summary.

**Example:**
```python
summary = await mapper.get_cluster_pressure_summary()
print(f"Volatile clusters: {summary['volatile_clusters']}")
print(f"Total hotspots: {summary['total_hotspot_beliefs']}")
```

#### `async get_escalating_conflicts(time_window_days: int = 7) -> List[Tuple[Belief, PressureTrend]]`

Identifies beliefs with escalating pressure trends.

**Example:**
```python
escalating = await mapper.get_escalating_conflicts()
for belief, trend in escalating:
    print(f"Escalating: {belief.statement} (slope: {trend.trend_slope:.4f})")
```

#### `async export_pressure_map_json(include_clusters: bool = True, include_trends: bool = True) -> Dict[str, Any]`

Exports complete pressure analysis as JSON.

**Example:**
```python
export_data = await mapper.export_pressure_map_json()
with open('pressure_map.json', 'w') as f:
    json.dump(export_data, f, indent=2)
```

### Natural Language Explanation Methods

#### `async get_pressure_explanations(top_n: int = 5) -> List[Dict[str, Any]]`

Generates natural language explanations for top pressure hotspots.

**Example:**
```python
explanations = await mapper.get_pressure_explanations(3)
for explanation in explanations:
    print(f"Belief: {explanation['belief']['statement']}")
    print(f"Pressure: {explanation['pressure_score']['score']:.3f}")
    print(f"Analysis: {explanation['pressure_analysis']['source_of_pressure']}")
```

#### `async get_cluster_explanations(cluster_id: Optional[int] = None) -> List[Dict[str, Any]]`

Provides detailed explanations for cluster instability.

**Example:**
```python
cluster_explanations = await mapper.get_cluster_explanations()
for explanation in cluster_explanations:
    diagnosis = explanation['cluster_diagnosis']
    print(f"Cluster {explanation['cluster_info']['cluster_id']}: {diagnosis['description']}")
```

### Monitoring Methods

#### `start_monitoring() -> None`

Starts runtime pressure monitoring in a separate thread.

**Example:**
```python
mapper.start_monitoring()
# Monitoring runs continuously until stopped
```

#### `stop_monitoring() -> None`

Stops runtime monitoring thread.

**Example:**
```python
mapper.stop_monitoring()
```

### Utility Methods

#### `calculate_pressure_score(belief: Belief, contradictions: List[Contradiction]) -> PressureScore`

Calculates pressure score for a single belief (primarily for testing).

#### `_log_instability_event(belief_id: UUID, event_type: str, **kwargs) -> None`

Logs instability events to the journal system.

## JSON Export Schema

### Top-Level Structure

```json
{
  "timestamp": "2025-01-25T10:30:00Z",
  "pressure_threshold": 0.6,
  "escalation_threshold": 0.1,
  "total_beliefs": 150,
  "unstable_beliefs": 12,
  "pressure_scores": { ... },
  "cluster_analysis": { ... },
  "trend_analysis": { ... }
}
```

### Pressure Score Schema

```json
{
  "belief_id": "uuid-string",
  "score": 0.75,
  "confidence_weight": 0.9,
  "importance_weight": 0.8,
  "decay_weight": 0.85,
  "conflict_count": 3,
  "contradiction_ids": ["uuid1", "uuid2", "uuid3"],
  "timestamp": "2025-01-25T10:30:00Z"
}
```

### Cluster Analysis Schema

```json
{
  "total_clusters": 15,
  "volatile_clusters": 3,
  "average_cluster_pressure": 0.45,
  "max_cluster_pressure": 0.88,
  "total_hotspot_beliefs": 8,
  "clusters": [
    {
      "cluster_id": 0,
      "belief_ids": ["uuid1", "uuid2"],
      "average_pressure": 0.72,
      "max_pressure": 0.85,
      "total_conflicts": 5,
      "cluster_size": 2,
      "semantic_coherence": 0.78,
      "hotspot_beliefs": ["uuid1"],
      "timestamp": "2025-01-25T10:30:00Z"
    }
  ]
}
```

### Trend Analysis Schema

```json
{
  "trends": [
    {
      "belief_id": "uuid-string",
      "trend_slope": 0.15,
      "trend_direction": "escalating",
      "recent_scores": [0.5, 0.6, 0.7, 0.8, 0.9],
      "time_window_days": 7,
      "confidence_interval": [0.4, 1.0],
      "timestamp": "2025-01-25T10:30:00Z"
    }
  ],
  "escalating_count": 5,
  "resolving_count": 3,
  "stable_count": 142
}
```

### Explanation Schema

```json
{
  "belief": {
    "id": "uuid-string",
    "statement": "Belief statement text",
    "confidence": 0.9,
    "importance": 0.8
  },
  "pressure_score": { ... },
  "opposing_belief": { ... },
  "explanation": {
    "explanation": "Natural language explanation",
    "keywords_in_conflict": ["autonomous", "controlled"],
    "conflict_type": "value",
    "severity": "hard",
    "resolution_strategies": ["Strategy 1", "Strategy 2"]
  },
  "pressure_analysis": {
    "source_of_pressure": {
      "primary_sources": [
        {
          "type": "high_confidence_contradiction",
          "description": "High-confidence belief facing contradictions",
          "severity": "high"
        }
      ]
    },
    "recommended_actions": ["Action 1", "Action 2"],
    "urgency_level": "high"
  }
}
```

## Usage Examples

### Basic Pressure Analysis

```python
from belief_pressure_mapper import BeliefPressureMapper

# Initialize mapper
mapper = BeliefPressureMapper()

# Generate pressure heatmap
heatmap = await mapper.generate_heatmap()

# Find unstable beliefs
unstable_beliefs = [
    (belief_id, score) for belief_id, score in heatmap.items()
    if score.score > mapper.pressure_threshold
]

print(f"Found {len(unstable_beliefs)} unstable beliefs")
```

### Cluster Analysis and Monitoring

```python
# Perform cluster analysis
clusters = await mapper.perform_cluster_analysis()

# Identify volatile clusters
volatile_clusters = [c for c in clusters if len(c.hotspot_beliefs) > 0]

for cluster in volatile_clusters:
    print(f"Volatile Cluster {cluster.cluster_id}:")
    print(f"  Average pressure: {cluster.average_pressure:.3f}")
    print(f"  Hotspot beliefs: {len(cluster.hotspot_beliefs)}")
    print(f"  Semantic coherence: {cluster.semantic_coherence:.3f}")
```

### Trend Analysis and Alerting

```python
# Analyze pressure trends
trends = await mapper.analyze_pressure_trends(14)

# Filter escalating trends
escalating_trends = [t for t in trends if t.trend_direction == "escalating"]

if escalating_trends:
    print(f"⚠️ {len(escalating_trends)} beliefs showing escalating pressure:")
    for trend in escalating_trends[:5]:  # Top 5
        print(f"  Belief {trend.belief_id}: slope {trend.trend_slope:.4f}")
```

### Runtime Monitoring Setup

```python
import asyncio
import signal

# Configure monitoring
config = {
    'monitoring_interval': 300,  # 5 minutes
    'pressure_threshold': 0.7,
    'escalation_threshold': 0.1
}

mapper = BeliefPressureMapper(config=config)

# Start monitoring
mapper.start_monitoring()

# Set up graceful shutdown
def signal_handler(signum, frame):
    print("Shutting down monitoring...")
    mapper.stop_monitoring()
    exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

print("Pressure monitoring active. Press Ctrl+C to stop.")
try:
    while True:
        await asyncio.sleep(1)
except KeyboardInterrupt:
    signal_handler(None, None)
```

### Custom Analysis Pipeline

```python
async def custom_pressure_analysis():
    mapper = BeliefPressureMapper()
    
    # Step 1: Generate heatmap
    print("Generating pressure heatmap...")
    heatmap = await mapper.generate_heatmap()
    
    # Step 2: Cluster analysis
    print("Performing cluster analysis...")
    clusters = await mapper.perform_cluster_analysis()
    
    # Step 3: Trend analysis
    print("Analyzing pressure trends...")
    trends = await mapper.analyze_pressure_trends()
    
    # Step 4: Generate explanations
    print("Generating explanations...")
    explanations = await mapper.get_pressure_explanations(10)
    
    # Step 5: Export results
    print("Exporting analysis results...")
    export_data = await mapper.export_pressure_map_json()
    
    # Analysis summary
    print(f"\n📊 Pressure Analysis Summary:")
    print(f"  Total beliefs analyzed: {len(heatmap)}")
    print(f"  Unstable beliefs: {export_data['unstable_beliefs']}")
    print(f"  Clusters identified: {len(clusters)}")
    print(f"  Volatile clusters: {len([c for c in clusters if len(c.hotspot_beliefs) > 0])}")
    print(f"  Escalating trends: {sum(1 for t in trends if t.trend_direction == 'escalating')}")
    print(f"  Explanations generated: {len(explanations)}")
    
    return export_data

# Run analysis
results = await custom_pressure_analysis()
```

### Integration with Frontend Visualization

```python
from flask import Flask, jsonify
import asyncio

app = Flask(__name__)
mapper = BeliefPressureMapper()

@app.route('/api/pressure-map')
async def get_pressure_map():
    """API endpoint for frontend pressure visualization"""
    try:
        export_data = await mapper.export_pressure_map_json()
        return jsonify(export_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/high-pressure-beliefs/<int:count>')
async def get_high_pressure_beliefs(count):
    """API endpoint for high pressure beliefs"""
    try:
        high_pressure = await mapper.get_high_pressure_beliefs(count)
        
        result = []
        for belief, score in high_pressure:
            result.append({
                'belief': {
                    'id': str(belief.id),
                    'statement': belief.statement,
                    'confidence': belief.confidence,
                    'importance': belief.importance
                },
                'pressure_score': score.to_dict()
            })
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/escalating-conflicts')
async def get_escalating_conflicts():
    """API endpoint for escalating conflicts"""
    try:
        escalating = await mapper.get_escalating_conflicts()
        
        result = []
        for belief, trend in escalating:
            result.append({
                'belief': {
                    'id': str(belief.id),
                    'statement': belief.statement[:100] + '...'  # Truncate for API
                },
                'trend': trend.to_dict()
            })
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
```

## Integration Guide

### Integration with BeliefRegistry

The BeliefPressureMapper requires a BeliefRegistry instance for accessing beliefs and contradictions:

```python
from belief_registry import BeliefRegistry
from belief_pressure_mapper import BeliefPressureMapper

# Use existing registry
registry = BeliefRegistry()
mapper = BeliefPressureMapper(belief_registry=registry)

# Or let mapper create its own
mapper = BeliefPressureMapper()  # Creates default registry
```

### Integration with ContradictionExplainer

For natural language explanations, provide a ContradictionExplainer instance:

```python
from contradiction_explainer import ContradictionExplainer
from belief_pressure_mapper import BeliefPressureMapper

explainer = ContradictionExplainer()
mapper = BeliefPressureMapper(contradiction_explainer=explainer)

# Generate explanations
explanations = await mapper.get_pressure_explanations()
```

### Integration with JournalEngine

The mapper automatically logs instability events to the journal system:

```python
# Events are automatically logged with these tags:
# - "belief_instability"
# - event type (e.g., "pressure_threshold_exceeded")
# - "pressure_monitoring"

# Journal entries include metadata:
# - belief_id
# - event_type  
# - current_score
# - trigger_reason
# - timestamp
```

### Custom Event Handlers

You can extend the mapper with custom event handlers:

```python
class CustomPressureMapper(BeliefPressureMapper):
    
    def _log_instability_event(self, belief_id, event_type, **kwargs):
        # Call parent method
        super()._log_instability_event(belief_id, event_type, **kwargs)
        
        # Add custom handling
        if event_type == "pressure_threshold_exceeded":
            self._send_alert(belief_id, kwargs.get('current_score'))
        elif event_type == "escalating_trend":
            self._trigger_investigation(belief_id, kwargs.get('trend_slope'))
    
    def _send_alert(self, belief_id, score):
        # Custom alert logic
        pass
    
    def _trigger_investigation(self, belief_id, slope):
        # Custom investigation logic
        pass
```

## Performance Considerations

### Memory Usage

- **Embedding Model**: ~500MB RAM for sentence-transformers model
- **History Storage**: ~1KB per belief per history entry
- **Cluster Analysis**: O(n²) memory for similarity matrix
- **Monitoring Thread**: Minimal overhead (~10MB)

### Processing Time

| Operation | Typical Time | Scaling |
|-----------|-------------|---------|
| Pressure Calculation | 1ms per belief | O(n) |
| Heatmap Generation | 10ms per 100 beliefs | O(n) |
| Cluster Analysis | 100ms per 100 beliefs | O(n²) |
| Trend Analysis | 50ms per 1000 history entries | O(n) |
| Explanation Generation | 500ms per explanation | O(1) |

### Optimization Strategies

#### 1. Batch Processing

```python
# Process beliefs in batches for large datasets
config = {
    'embedding_batch_size': 50,  # Reduce memory usage
    'max_beliefs_to_compare': 1000  # Limit cluster analysis
}
```

#### 2. Caching

```python
# Cache embeddings to avoid recomputation
class CachedPressureMapper(BeliefPressureMapper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._embedding_cache = {}
    
    def _get_cached_embeddings(self, statements):
        # Check cache first
        cache_key = hash(tuple(statements))
        if cache_key in self._embedding_cache:
            return self._embedding_cache[cache_key]
        
        # Compute and cache
        embeddings = self._get_embedding_model().encode(statements)
        self._embedding_cache[cache_key] = embeddings
        return embeddings
```

#### 3. Asynchronous Processing

```python
# Use async/await for I/O operations
async def parallel_analysis():
    mapper = BeliefPressureMapper()
    
    # Run multiple analyses concurrently
    heatmap_task = mapper.generate_heatmap()
    trends_task = mapper.analyze_pressure_trends()
    
    heatmap, trends = await asyncio.gather(heatmap_task, trends_task)
    return heatmap, trends
```

#### 4. Monitoring Interval Tuning

```python
# Adjust monitoring frequency based on system load
config = {
    'monitoring_interval': 600,  # 10 minutes for high-volume systems
    'history_log_rotation': 5000  # More frequent rotation
}
```

### Resource Limits

- **Maximum Beliefs**: 10,000 (configurable via `MAX_BELIEFS_TO_COMPARE`)
- **History Retention**: 10,000 entries (configurable via `MAX_HISTORY_ENTRIES`)
- **Cluster Count**: Limited by DBSCAN performance (~1000 beliefs practical limit)
- **Concurrent Monitoring**: Single thread per mapper instance

## Troubleshooting

### Common Issues

#### 1. High Memory Usage

**Symptoms**: Process memory usage exceeds expected limits

**Solutions**:
- Reduce `embedding_batch_size` in config
- Implement embedding caching
- Increase history log rotation frequency
- Limit beliefs processed with `MAX_BELIEFS_TO_COMPARE`

```python
config = {
    'embedding_batch_size': 25,
    'max_history_entries': 5000,
    'max_beliefs_to_compare': 500
}
```

#### 2. Slow Cluster Analysis

**Symptoms**: `perform_cluster_analysis()` takes very long

**Solutions**:
- Reduce the number of beliefs analyzed
- Adjust DBSCAN parameters for faster clustering
- Use pre-computed embeddings

```python
config = {
    'cluster_eps': 0.5,  # Larger epsilon = fewer, larger clusters
    'cluster_min_samples': 3  # Higher minimum = fewer clusters
}
```

#### 3. Missing Pressure History

**Symptoms**: Trend analysis returns empty results

**Solutions**:
- Check if history log path is writable
- Verify monitoring is running
- Check for log rotation issues

```python
# Debug history logging
history = mapper._load_pressure_history()
print(f"History entries: {len(history)}")

# Check log file permissions
import os
log_path = mapper.history_log_path
print(f"Log exists: {log_path.exists()}")
print(f"Log writable: {os.access(log_path.parent, os.W_OK)}")
```

#### 4. Explanation Generation Fails

**Symptoms**: `get_pressure_explanations()` returns empty results

**Solutions**:
- Verify ContradictionExplainer is properly initialized
- Check if beliefs have actual contradictions
- Ensure belief registry is accessible

```python
# Debug explanation generation
contradictions = await mapper.belief_registry.get_all_contradictions()
print(f"Total contradictions: {len(contradictions)}")

if not contradictions:
    print("No contradictions found - explanations require conflicts")
```

#### 5. Monitoring Thread Issues

**Symptoms**: Monitoring stops unexpectedly

**Solutions**:
- Check for exceptions in monitoring loop
- Verify thread safety of async operations
- Implement monitoring health checks

```python
# Add monitoring health check
import threading

def check_monitoring_health(mapper):
    if not mapper.monitoring_active:
        print("❌ Monitoring is inactive")
    elif not mapper.monitoring_thread.is_alive():
        print("❌ Monitoring thread has died")
        mapper.start_monitoring()  # Restart
    else:
        print("✅ Monitoring is healthy")

# Run health check periodically
def health_check_loop(mapper):
    while True:
        time.sleep(300)  # Check every 5 minutes
        check_monitoring_health(mapper)

threading.Thread(target=health_check_loop, args=(mapper,), daemon=True).start()
```

### Debugging Tools

#### 1. Verbose Logging

```python
import logging

# Enable debug logging
logging.getLogger("belief_pressure_mapper").setLevel(logging.DEBUG)

# Add custom handler
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(
    '[%(asctime)s] [%(levelname)s] %(name)s: %(message)s'
))
logging.getLogger("belief_pressure_mapper").addHandler(handler)
```

#### 2. Performance Profiling

```python
import time
import cProfile

def profile_pressure_analysis():
    mapper = BeliefPressureMapper()
    
    def run_analysis():
        return asyncio.run(mapper.generate_heatmap())
    
    # Profile the analysis
    cProfile.run('run_analysis()', 'pressure_analysis.prof')

# Analyze profile results
# python -m pstats pressure_analysis.prof
```

#### 3. Memory Monitoring

```python
import tracemalloc
import psutil
import os

def monitor_memory_usage():
    tracemalloc.start()
    
    mapper = BeliefPressureMapper()
    
    # Before analysis
    process = psutil.Process(os.getpid())
    memory_before = process.memory_info().rss / 1024 / 1024  # MB
    
    # Run analysis
    heatmap = await mapper.generate_heatmap()
    
    # After analysis
    memory_after = process.memory_info().rss / 1024 / 1024  # MB
    
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    print(f"Memory usage: {memory_before:.1f}MB → {memory_after:.1f}MB")
    print(f"Peak traced memory: {peak / 1024 / 1024:.1f}MB")
```

### Error Codes and Solutions

| Error Code | Description | Solution |
|------------|-------------|----------|
| PRESS_001 | History log rotation failed | Check disk space and permissions |
| PRESS_002 | Embedding model loading failed | Verify model files and network access |
| PRESS_003 | Cluster analysis timeout | Reduce dataset size or adjust parameters |
| PRESS_004 | Journal logging failed | Check journal engine configuration |
| PRESS_005 | Trend calculation failed | Verify sufficient history data |

For additional support, check the system logs and enable debug logging for detailed error information.