# AI Podcast Agent - Development Sprint Plan

## Overview
4 focused sprints to complete the pipeline logic, with each sprint building on the previous one.

## Sprint 1: Core Ingestion (Day 1-2)
**Goal**: Get articles into the database from RSS feeds

### Tasks:
1. **RSS Feed Fetcher** (2-3 hours)
   - `aipod/ingestion/rss_fetcher.py`
   - Fetch and parse RSS feeds concurrently
   - Extract: title, link, published date, description
   - Handle failures gracefully (timeout, 404, invalid XML)
   - Return structured feed items

2. **HTML Fetcher & Text Extractor** (2-3 hours)
   - `aipod/ingestion/article_fetcher.py`
   - Fetch HTML with retries and timeouts
   - Extract main content using trafilatura
   - Handle paywalls and errors
   - Normalize URLs and detect outlets

3. **Article Storage & Deduplication** (2-3 hours)
   - `aipod/db/articles.py`
   - Upsert articles with content hash
   - Check for duplicates by URL and hash
   - Store extracted text to filesystem
   - Link articles to runs

### Deliverable:
- Can fetch RSS feeds and store articles in database
- Test with: `python -m aipod.ingestion.test_fetch`

## Sprint 2: Ranking System (Day 2-3)
**Goal**: Score and rank articles based on multiple factors

### Tasks:
1. **Scoring Components** (3-4 hours)
   - `aipod/ranking/scorers.py`
   - RecencyScorer: exponential decay from publish date
   - SourceScorer: weight from source config
   - TopicScorer: keyword matching with boost/suppress lists
   - NoveltyScorer: check against recent runs

2. **Article Ranker** (2-3 hours)
   - `aipod/ranking/ranker.py`
   - Combine scores with configurable weights
   - Generate explainable score breakdowns
   - Select top N stories
   - Store rankings in database

### Deliverable:
- Can rank articles with explainable scores
- Test with: `python -m aipod.ranking.test_rank`

## Sprint 3: LLM Integration (Day 3-4)
**Goal**: Generate show notes and scripts using LLMs

### Tasks:
1. **LLM Provider Interface** (2 hours)
   - `aipod/generation/llm_provider.py`
   - Abstract base class with summarize/generate methods
   - OpenAI implementation
   - Error handling and retries
   - Token/cost tracking

2. **Show Notes Generator** (3 hours)
   - `aipod/generation/show_notes.py`
   - Summarize each article into bullet points
   - Group by category
   - Format as clean Markdown
   - Include links and metadata

3. **Script Generator** (3 hours)
   - `aipod/generation/script.py`
   - Generate coherent narration from summaries
   - Target specified reading time
   - Natural transitions between stories
   - Appropriate for TTS

### Deliverable:
- Can generate show_notes.md and script.txt
- Test with: `python -m aipod.generation.test_generate`

## Sprint 4: Pipeline Orchestration (Day 4-5)
**Goal**: Wire everything together in the run command

### Tasks:
1. **Run Command Orchestrator** (4 hours)
   - `aipod/cli/run.py`
   - Create run record in database
   - Execute pipeline stages in order
   - Handle stage failures gracefully
   - Write artifacts to run directory

2. **Progress Tracking & Error Handling** (2 hours)
   - Rich progress bars for each stage
   - Detailed logging to file
   - Partial run recovery
   - Stats collection and storage

3. **End-to-End Testing** (2 hours)
   - Test with real RSS feeds
   - Verify all artifacts generated
   - Check database consistency
   - Performance optimization

### Deliverable:
- Complete working pipeline: `aipod run --minutes 12`
- All artifacts generated in run folder

## Development Order & Dependencies

```
Sprint 1.1 (RSS Fetcher)
    ↓
Sprint 1.2 (Article Fetcher) 
    ↓
Sprint 1.3 (Storage)
    ↓
Sprint 2.1 (Scorers) ←── Can be done in parallel with Sprint 3.1
    ↓
Sprint 2.2 (Ranker)
    ↓
Sprint 3.2 (Show Notes) ← Depends on Sprint 3.1 (LLM Provider)
    ↓
Sprint 3.3 (Script)
    ↓
Sprint 4.1 (Orchestrator) ← Integrates all previous work
    ↓
Sprint 4.2 (Polish)
    ↓
Sprint 4.3 (Testing)
```

## Quick Wins Strategy

1. **Start with Sprint 1.1-1.3** - Get data flowing into the system
2. **Parallel work**: While testing ingestion, start on LLM provider (Sprint 3.1)
3. **Mock data**: Create sample ranked articles to test generation while ranking is being built
4. **Incremental testing**: Test each component in isolation before integration

## Time Estimates

- **Sprint 1**: 6-8 hours (Core Ingestion)
- **Sprint 2**: 5-6 hours (Ranking) 
- **Sprint 3**: 8 hours (LLM Integration)
- **Sprint 4**: 8 hours (Orchestration & Testing)

**Total**: ~27-30 hours of focused development

## Success Criteria

After completing all sprints, running `aipod run` should:
1. ✅ Fetch latest articles from all enabled RSS sources
2. ✅ Extract and store article content
3. ✅ Deduplicate articles
4. ✅ Rank articles with explainable scores
5. ✅ Generate structured show notes
6. ✅ Generate narration-ready script
7. ✅ Save all artifacts to dated run folder
8. ✅ Handle errors gracefully without crashing