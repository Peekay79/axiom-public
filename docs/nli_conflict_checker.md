# NLI Conflict Checker Documentation

## Overview

The Natural Language Inference (NLI) Conflict Checker is a semantic contradiction detection system that replaces the previous mock string-matching logic with real sentence-transformer embeddings. This system identifies conflicting statements based on semantic similarity analysis and serves as a critical component for belief contradiction detection, reflexive audits, and cognitive coherence validation.

## Architecture

### Core Components

1. **Semantic Analysis Engine**: Uses sentence-transformers to compute semantic embeddings
2. **Similarity Scoring**: Cosine similarity between normalized embeddings
3. **Threshold-based Classification**: Multi-tier scoring system for contradiction detection
4. **Fallback Analysis**: String-based analysis when embeddings fail
5. **Edge Case Handling**: Robust validation for various input scenarios

### Model Configuration

- **Primary Model**: `sentence-transformers/all-MiniLM-L6-v2`
  - Lightweight (22MB)
  - Good semantic understanding
  - Fast inference time
  - Balanced accuracy/performance trade-off
- **Environment Variable**: `NLI_EMBED_MODEL` (overrides default)
- **Device**: Auto-detects CUDA/CPU with graceful fallback

## Scoring Logic

### Similarity Thresholds

```python
CONFLICT_THRESHOLD = 0.6     # Below this = likely contradiction
IDENTICAL_THRESHOLD = 0.95   # Above this = likely identical/paraphrase
NEUTRAL_THRESHOLD = 0.8      # Between 0.6-0.8 = uncertain/neutral
```

### Decision Matrix

| Similarity Score | Classification | Confidence | Explanation |
|-----------------|----------------|------------|-------------|
| ≥ 0.95 | No Conflict | High (≥0.95) | Identical or paraphrases |
| 0.6 - 0.95 | No Conflict | Moderate | Neutral or related statements |
| < 0.6 OR negation/sentiment opposition | **Conflict** | High (1.0 - similarity) | Likely contradictory |

### Enhanced Scoring

- **Negation Boost**: Adds +0.1 confidence when negation mismatch detected
- **Fallback Scoring**: Uses string-based analysis with different confidence ranges
- **Edge Case Handling**: Special confidence scores for empty/invalid inputs

## API Reference

### Primary Function

```python
def nli_check(a: str, b: str) -> Dict:
    """
    Determines whether statements `a` and `b` are contradictory using semantic analysis.
    
    Args:
        a (str): First statement to compare
        b (str): Second statement to compare
    
    Returns:
        Dict with keys:
            - "conflict" (bool): True if statements are contradictory
            - "confidence" (float): Confidence score (0.0 to 1.0)
            - "explanation" (str): Human-readable explanation
    """
```

### Batch Processing

```python
def nli_check_batch(text_pairs: list) -> list:
    """Process multiple text pairs for contradiction detection."""
```

### Health Check

```python
def check_nli_health() -> Dict:
    """Verify that the NLI system is working correctly."""
```

## Usage Examples

### Basic Usage

```python
from nli_conflict_checker import nli_check

# Clear contradiction
result = nli_check("The sky is blue", "The sky is not blue")
# Expected: {"conflict": True, "confidence": ~0.8, "explanation": "..."}

# Paraphrase (no conflict)
result = nli_check("I love coffee", "I enjoy drinking coffee")
# Expected: {"conflict": False, "confidence": ~0.9, "explanation": "..."}

# Unrelated statements
result = nli_check("Today is Monday", "I like pizza")
# Expected: {"conflict": False, "confidence": ~0.6, "explanation": "..."}
```

### Batch Processing

```python
from nli_conflict_checker import nli_check_batch

pairs = [
    ("Statement A", "Statement B"),
    ("Another A", "Another B"),
]
results = nli_check_batch(pairs)
```

### System Health Check

```python
from nli_conflict_checker import check_nli_health

health = check_nli_health()
print(f"Model loaded: {health['model_loaded']}")
print(f"Test passed: {health['test_passed']}")
```

## Fallback Behavior

When sentence-transformers is unavailable or fails, the system automatically falls back to string-based analysis:

### Fallback Logic

1. **Exact Match**: Identical strings after normalization
2. **Substring Detection**: One text contained in another
3. **Negation Mismatch**: Significant difference in negation keywords
4. **Default Neutral**: No clear patterns detected

### Negation Keywords

```python
NEGATION_KEYWORDS = [
    "not", "never", "no", "cannot", "can't", "won't", "wouldn't",
    "shouldn't", "couldn't", "isn't", "aren't", "wasn't", "weren't",
    "haven't", "hasn't", "hadn't", "doesn't", "didn't", "don't",
    "fail to", "unable to", "impossible", "lack", "without",
    "refuse", "reject", "deny", "oppose", "against"
]
```

## Performance Characteristics

### Model Loading

- **First Call**: ~2-3 seconds (model download and initialization)
- **Subsequent Calls**: Cached, near-instantaneous
- **Memory Usage**: ~150MB RAM for model weights

### Inference Speed

- **Short texts** (<50 words): ~10-50ms
- **Medium texts** (50-200 words): ~50-100ms
- **Long texts** (>200 words): ~100-200ms
- **Batch processing**: Significantly faster per item

### Resource Requirements

- **CPU**: Works on any modern CPU
- **GPU**: Automatically uses CUDA if available (3-5x speedup)
- **Memory**: 150MB model + 50MB per batch
- **Disk**: 22MB for model weights (auto-downloaded)

## Error Handling

### Graceful Degradation

1. **Import Failure**: Falls back to string analysis
2. **Model Load Failure**: Falls back to string analysis
3. **Inference Failure**: Returns fallback result with error logging
4. **Invalid Input**: Returns structured error response

### Logging

```python
import logging
logger = logging.getLogger('nli_conflict_checker')
logger.setLevel(logging.INFO)
```

Log levels:
- **INFO**: Model loading, fallback activation
- **DEBUG**: Similarity scores, detailed analysis
- **ERROR**: Model failures, inference errors
- **WARNING**: Import failures, degraded performance

## Configuration

### Environment Variables

```bash
# Override default model
export NLI_EMBED_MODEL="sentence-transformers/all-mpnet-base-v2"

# Enable debug logging
export LOG_LEVEL=DEBUG
```

### Custom Thresholds

```python
# Override in your code (not recommended)
import nli_conflict_checker
nli_conflict_checker.CONFLICT_THRESHOLD = 0.4
nli_conflict_checker.IDENTICAL_THRESHOLD = 0.95
```

## Integration Points

### Current Usage

- **contradiction_resolver.py**: Primary consumer for belief contradiction detection
- **Cognitive systems**: Reflexive audits and coherence validation
- **Memory systems**: Conflict detection in belief ingestion

### Integration Pattern

```python
from nli_conflict_checker import nli_check

def detect_belief_conflicts(belief_a, belief_b):
    result = nli_check(belief_a["content"], belief_b["content"])
    if result["conflict"] and result["confidence"] > 0.7:
        log_contradiction(belief_a, belief_b, result)
        return True
    return False
```

## Testing

### Unit Test Coverage

- ✅ Identical statements detection
- ✅ Clear contradiction detection  
- ✅ Paraphrase handling
- ✅ Edge cases (empty, invalid inputs)
- ✅ Fallback behavior validation
- ✅ Batch processing
- ✅ Performance with long texts
- ✅ Special characters and Unicode
- ✅ Health check functionality

### Running Tests

```bash
# Run all tests
python test_nli_conflict_checker.py

# Run specific test class
python -m unittest test_nli_conflict_checker.TestNLIConflictChecker

# Run with verbose output
python -m unittest test_nli_conflict_checker -v
```

## Future Improvements

### Short-term (Next Sprint)

1. **Fine-tuned Models**: Train domain-specific contradiction detection
2. **Caching Layer**: Redis/memory cache for frequent comparisons
3. **Metrics Collection**: Performance and accuracy tracking
4. **Threshold Optimization**: A/B testing for optimal thresholds

### Medium-term (Next Quarter)

1. **Multi-language Support**: Non-English contradiction detection
2. **Contextual Analysis**: Consider surrounding context in decisions
3. **Confidence Calibration**: Improve confidence score accuracy
4. **Ensemble Methods**: Combine multiple models for better accuracy

### Long-term (Future Versions)

1. **Real NLI Models**: Dedicated entailment/contradiction classifiers
2. **Reasoning Chains**: Explain why statements contradict
3. **Temporal Awareness**: Handle time-sensitive contradictions
4. **Domain Adaptation**: Automatically adapt to domain-specific language

## Troubleshooting

### Common Issues

1. **Model Download Fails**
   ```bash
   # Manual download
   python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"
   ```

2. **Performance Issues**
   ```bash
   # Check GPU availability
   python -c "import torch; print(torch.cuda.is_available())"
   ```

3. **Memory Issues**
   ```bash
   # Reduce batch size or use CPU-only mode
   export CUDA_VISIBLE_DEVICES=""
   ```

### Health Check

```python
from nli_conflict_checker import check_nli_health
health = check_nli_health()
if not health["test_passed"]:
    print("System not working correctly!")
    print(health)
```

## Dependencies

### Required

- `sentence-transformers>=5.0.0`
- `torch>=2.0.0`
- `numpy>=1.24.0`

### Optional

- `transformers>=4.21.0` (usually bundled with sentence-transformers)
- CUDA toolkit for GPU acceleration

## Security Considerations

- **Input Validation**: All inputs validated and sanitized
- **Resource Limits**: Model memory usage bounded
- **Error Handling**: No sensitive information in error messages
- **Logging**: No user data logged at INFO level or above

---

*Last Updated: 2025-01-25*
*Version: 2.0.0*
*Author: Axiom AI Systems Team*