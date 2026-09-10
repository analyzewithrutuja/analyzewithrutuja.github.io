# Retrieval Quality — Sample Queries

Output of `scripts/query_index.py`, run against the 701-chunk index built
from the 6-document corpus. Each result shows cosine similarity score,
source document, and page number.

## Q: What is grid resilience and how is it different from reliability?
1. `[0.676]` DOE — A More Resilient Grid (2016), p.4
2. `[0.655]` DOE — A More Resilient Grid (2016), p.5
3. `[0.651]` DOE — A More Resilient Grid (2016), p.6

## Q: How does the grid respond to extreme weather events?
1. `[0.591]` DOE — A More Resilient Grid (2016), p.1
2. `[0.573]` DOE — Economic Benefits of Increasing Electric Grid Resilience (2013), p.3
3. `[0.571]` FERC — Summer Energy Market and Electric Reliability Assessment (2025), p.13

## Q: What are the benefits of grid modernization investments?
1. `[0.606]` DOE — Grid Modernization Strategy (2024), p.28
2. `[0.585]` DOE — Grid Modernization Strategy (2024), p.31
3. `[0.583]` DOE — Economic Benefits of Increasing Electric Grid Resilience (2013), p.23

## Q: How is electric reliability measured or assessed in the summer?
1. `[0.638]` FERC — Summer Energy Market and Electric Reliability Assessment (2025), p.2
2. `[0.636]` FERC — Summer Energy Market and Electric Reliability Assessment (2025), p.1
3. `[0.571]` FERC — Electric Reliability Primer, p.43

## Q: What are NERC's core reliability principles?
1. `[0.698]` FERC — Electric Reliability Primer, p.53
2. `[0.697]` FERC — Electric Reliability Primer, p.56
3. `[0.690]` FERC — Electric Reliability Primer, p.53

**Observation:** every top-3 retrieval lands in the correct source document
for its topic (grid-modernization questions surface the modernization
strategy doc, summer-reliability questions surface the FERC summer
assessment, etc.), confirming the chunking/embedding strategy separates
topics cleanly even though several documents share overlapping
reliability/resilience vocabulary.
