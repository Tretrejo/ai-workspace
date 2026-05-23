---
name: data-engineering-2026
description: >
  Modern Python data engineering stack for 2026 — covering when to use Polars over
  Pandas, Bytewax for stream processing, Turbovec for vector search, and the full
  toolkit for building reliable data pipelines. Use this skill whenever someone is
  building a data pipeline, ETL workflow, data transformation, stream processing
  system, or vector search index; whenever Pandas is mentioned for a task where Polars
  would be better; whenever someone asks which Python data library to use; or for
  queries involving large DataFrames, real-time data, embeddings, or data quality.
  Also trigger for phrases like "data pipeline," "ETL," "transform data," "streaming
  pipeline," "vector index," "slow Pandas," "out of memory on DataFrame," or
  "data engineering stack." Always check the data size, latency requirements, and
  deployment context before recommending — these determine the right tool.
---
# Data Engineering 2026 Skill
The Python data ecosystem has shifted significantly. Using the right tool for each job
now means knowing when to move beyond the incumbents.
---
## The 2026 Stack at a Glance
| Problem | Old default | Better choice | When to switch |
|---|---|---|---|
| DataFrame operations | Pandas | **Polars** | Data > 100K rows or speed matters |
| Real-time streaming | Flink / raw Kafka | **Bytewax** | Python-native team, <100K events/sec |
| Vector search | FAISS | **Turbovec** | ARM hardware, no codebook training needed |
| Workflow orchestration | Airflow | **Prefect / Dagster** | Teams that want Python-native observability |
| Data validation | Manual assertions | **Pandera** | Any production pipeline |
---
## Polars — Replacing Pandas for Most Workloads
Use Polars when: DataFrame > ~100K rows, running in a pipeline, hitting memory limits,
need multi-core parallelism, or want lazy evaluation.
```python
import polars as pl
# Lazy reading — doesn't load until needed
df = pl.scan_csv("data.csv")
df = pl.scan_parquet("data.parquet")
# Transforms with lazy evaluation, then collect
result = (
    df
    .filter(pl.col("date") > pl.lit("2024-01-01"))
    .group_by("region")
    .agg([
        pl.col("revenue").sum().alias("total_revenue"),
        pl.col("units").mean().alias("avg_units"),
        pl.len().alias("row_count")
    ])
    .sort("total_revenue", descending=True)
    .collect()
)
# Window functions
df.with_columns([
    pl.col("revenue").rolling_mean(7).over("region").alias("7d_avg"),
    pl.col("revenue").rank("dense").over("region").alias("revenue_rank")
])
# Streaming for files larger than RAM
result = (
    pl.scan_csv("huge.csv")
    .group_by("category")
    .agg(pl.col("amount").sum())
    .collect(streaming=True)
)
# Convert to/from Pandas when needed
pandas_df = polars_df.to_pandas()
polars_df = pl.from_pandas(pandas_df)
```
**Performance tips:**
- Prefer expressions over `map_elements` — vectorized is 10–100× faster
- Use `scan_*` for large files (lazy), `read_*` for small files (eager)
- Use `collect(streaming=True)` for files larger than RAM
---
## Bytewax — Python-Native Stream Processing
Use Bytewax when: real-time Python processing, windowing/stateful ops needed,
Kafka integration without boilerplate, <100K events/sec. Keep Flink for massive scale.
```python
import bytewax.operators as op
from bytewax.dataflow import Dataflow
from bytewax.inputs import KafkaSourceConfig, Source
from bytewax.outputs import StdOutSink
from datetime import timedelta
flow = Dataflow("pipeline")
kafka_input = KafkaSourceConfig(brokers=["localhost:9092"], topics=["events"])
stream = op.input("in", flow, Source.from_config(kafka_input))
def parse(msg):
    import json
    return json.loads(msg[1])
events = op.map("parse", stream, parse)
purchases = op.filter("filter", events, lambda e: e["type"] == "purchase")
# Tumbling window aggregation
windowed = op.collect_window(
    "window", purchases,
    clock=op.EventClock("timestamp", wait_for_system_duration=timedelta(seconds=5)),
    windower=op.TumblingWindow(length=timedelta(minutes=1), align_to=None)
)
def aggregate(key, events):
    return {"user_id": key, "total": sum(e["amount"] for e in events)}
aggregated = op.map("agg", windowed, lambda x: aggregate(*x))
op.output("out", aggregated, StdOutSink())
from bytewax.run import run_main
run_main(flow)
```
---
## Turbovec — Fast Vector Search Without Training
Use Turbovec when: ARM hardware (Apple Silicon, AWS Graviton), corpus changes frequently
(no retraining), or you need instant indexing. Keep FAISS for billion-scale or GPU use.
```python
import turbovec
import numpy as np
dim = 1536  # OpenAI embedding dimension
index = turbovec.TurboQuantIndex(dim=dim, bits=4)
embeddings = np.random.rand(10_000, dim).astype(np.float32)
index.add(embeddings, list(range(10_000)))
query = np.random.rand(1, dim).astype(np.float32)
distances, result_ids = index.search(query, k=10)
# Memory: 10M vectors at dim=1536
# FAISS float32: ~58 GB  |  Turbovec 4-bit: ~4 GB  |  No training required
```
---
## Data Validation — Pandera
```python
import pandera.polars as pa
import polars as pl
schema = pa.DataFrameSchema({
    "user_id":  pa.Column(pl.Int64, nullable=False),
    "email":    pa.Column(pl.Utf8, pa.Check.str_matches(r".+@.+\..+")),
    "revenue":  pa.Column(pl.Float64, pa.Check.greater_than_or_equal_to(0)),
})
validated_df = schema.validate(df)
```
---
## Parquet + DuckDB Pattern
```python
# Write
df.write_parquet("output.parquet", compression="zstd")
# Query Parquet with SQL — no server needed
import duckdb
result = duckdb.sql("""
    SELECT region, SUM(revenue) as total
    FROM read_parquet('data/*.parquet')
    WHERE date > '2024-01-01'
    GROUP BY region
""").pl()  # Returns Polars DataFrame
```
---
## When NOT to Use These Tools
- **Polars**: tiny datasets (<10K rows), libraries that require Pandas, no performance need
- **Bytewax**: massive scale (millions/sec), exactly-once guarantees needed → use Flink
- **Turbovec**: billion-scale indexes, GPU acceleration needed → use FAISS
- **Prefect/Dagster**: simple one-off scripts → cron is enough
