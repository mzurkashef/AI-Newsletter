# AI Newsletter System - Product Requirements Document

## 1. Executive Summary

The AI Newsletter System is an automated content aggregation and delivery platform that collects articles from multiple AI newsletter sources and video content from YouTube channels, processes them for relevance, and delivers curated daily updates via Telegram.

**Version**: 1.0
**Status**: Production Ready
**Last Updated**: 2025-11-24

---

## 2. Product Overview

### 2.1 Purpose

Automate the collection and distribution of AI-related content from:
- Multiple AI newsletter sources (RSS feeds)
- YouTube channels with transcript analysis
- Deliver curated summaries daily via Telegram

### 2.2 Target Users

- AI enthusiasts who want daily AI news updates
- Professionals tracking AI industry developments
- Users seeking consolidated AI content from multiple sources

### 2.3 Key Value Propositions

1. **Automated Collection** - No manual content gathering required
2. **Content Consolidation** - Multiple sources in one newsletter
3. **Smart Filtering** - Removes duplicate and blocked content
4. **YouTube Integration** - Extracts and summarizes video transcripts
5. **Reliable Delivery** - Direct Telegram integration for instant notifications
6. **Scheduled Execution** - Runs automatically via Windows Task Scheduler

---

## 3. Functional Requirements

### 3.1 Content Collection (Phase 1)

#### Newsletter Sources
- **Input**: Configured newsletter URLs from `config/sources.yaml`
- **Sources**:
  - Superhuman AI (https://superhuman.ai/newsletter)
  - The Rundown AI (https://www.therundown.ai)
  - DeepLearning.AI The Batch (https://www.deeplearning.ai/the-batch)
- **Processing**:
  - Parse RSS feeds using feedparser library
  - Set User-Agent headers to avoid blocking
  - Extract title, link, and summary from each article
  - Limit to 5 articles per source
- **Output**: List of article objects with metadata

#### YouTube Channels
- **Input**: Configured YouTube channel IDs from `config/sources.yaml`
- **Channels**:
  - Lev Selector (UCA4GfsgbI09cLzonTKryC6g)
  - IndyDevDan (UC_x36zCEGilGpB1m-V4gmjg)
- **Processing**:
  - Fetch latest 3 videos per channel using yt-dlp
  - Extract video transcripts using YouTubeTranscriptApi
  - Summarize transcript to 1-2 lines (first 150 characters)
  - Fallback to "Check the video for details" if no transcript available
- **Output**: List of video objects with summaries

#### Error Handling
- **Skip blocked/error pages** containing keywords:
  - "blocked", "unable to access", "not found", "error"
  - "forbidden", "page does not exist", "404", "403", "500", "access denied"
- **Graceful fallback**: Continue processing other sources if one fails
- **Logging**: All errors logged at WARNING level

### 3.2 Deduplication (Phase 2)

- **Input**: List of collected articles and videos
- **Processing**:
  - Compare article titles (case-insensitive)
  - Remove exact duplicate titles
  - Preserve order of first occurrence
- **Output**: List of 15-20 unique articles
- **Metrics**: Log count before and after deduplication

### 3.3 AI Processing (Phase 3)

- **Input**: Deduplicated articles
- **Processing** (Future Enhancement):
  - Filter for major AI announcements
  - Categorize by topic (max 4 categories)
  - Apply relevance threshold (0.7 default)
  - Generate AI-powered summaries (optional)
- **Current Status**: Placeholder phase for future expansion
- **Output**: Categorized and ranked articles

### 3.4 Newsletter Generation (Phase 4)

- **Input**: Processed articles from Phase 3
- **Format**:
  ```
  📰 **AI Newsletter - Daily Update**
  Generated: YYYY-MM-DD HH:MM:SS UTC

  📰 **News Headlines:**
  1. Article Title (max 80 chars)
     [Link URL]

  2. Article Title
     [Link URL]

  🎥 **YouTube Insights:**
  1. Video Title (max 80 chars)
     Summary: [1-2 line summary from transcript, max 150 chars]
     Channel: [Channel Name]
     [Video URL]

  ✅ Your AI Newsletter is running.
  ```
- **Content Limits**:
  - Max 8 news articles shown
  - Max 7 YouTube videos shown
  - Titles truncated to 80 characters
  - Summaries truncated to 150 characters
- **Output**: Formatted message string ready for delivery

### 3.5 Newsletter Delivery (Phase 5)

- **Input**: Formatted newsletter message
- **Delivery Method**:
  - Direct HTTP POST to Telegram Bot API
  - Endpoint: `https://api.telegram.org/bot{TOKEN}/sendMessage`
  - Payload: JSON with chat_id and text
  - Timeout: 30 seconds
- **Configuration** (from `.env`):
  - `TELEGRAM_BOT_TOKEN`: Bot authentication token
  - `TELEGRAM_CHAT_ID`: Target chat/channel ID
- **Response Handling**:
  - Success: Log message ID
  - API Error: Log error description
  - HTTP Error: Log HTTP status code and response
  - Connection Error: Log exception and continue
- **Output**: Message ID or error status

---

## 4. Non-Functional Requirements

### 4.1 Performance
- **Collection Time**: < 60 seconds for all sources
- **Processing Time**: < 10 seconds for deduplication and formatting
- **Delivery Time**: < 5 seconds to Telegram
- **Total Pipeline**: < 2 minutes end-to-end

### 4.2 Reliability
- **Error Recovery**: Continue processing if one source fails
- **Logging**: Comprehensive DEBUG, INFO, WARNING, ERROR logging
- **Database**: SQLite for source status tracking
- **Retry Logic**: Graceful fallback for API failures

### 4.3 Scalability
- **Current Capacity**:
  - Up to 10 newsletter sources
  - Up to 10 YouTube channels
  - 20 articles max per run
- **Future Scaling**: Database abstraction enables SQL database migration

### 4.4 Security
- **Credentials**: Stored in `.env` file (not in version control)
- **API Communication**: HTTPS for Telegram API
- **User-Agent Headers**: Prevents blocking by newsletter sources
- **Input Validation**: URL and title validation before processing

### 4.5 Maintainability
- **Modular Architecture**: Separate concerns for collection, deduplication, processing
- **Configuration Management**: YAML-based config for sources and settings
- **Logging**: Structured logging with timestamps and log levels
- **Code Organization**: Clear separation of concerns across modules

---

## 5. Technical Architecture

### 5.1 System Components

```
┌─────────────────────────────────────────┐
│   NewsletterPipeline (Main Orchestrator)│
└────────────────┬────────────────────────┘
                 │
      ┌──────────┴──────────┬──────────────┬──────────────┐
      │                     │              │              │
      v                     v              v              v
┌──────────────┐  ┌────────────────┐  ┌──────────┐  ┌─────────────┐
│ Collection   │  │ Deduplication  │  │ AI Proc. │  │ Newsletter  │
│ Orchestrator │  │ Engine         │  │ Engine   │  │ Assembler   │
└──────────────┘  └────────────────┘  └──────────┘  └─────────────┘
      │
    ┌─┴─┐
    │   │
    v   v
┌──────────────┐  ┌─────────────────┐
│ RSS Parser   │  │ YouTube Fetcher │
│ (feedparser) │  │ (yt-dlp)        │
└──────────────┘  └─────────────────┘
```

### 5.2 Data Flow

1. **Content Collection**: Fetch → Parse → Filter → Store
2. **Deduplication**: Compare titles → Remove duplicates → Log metrics
3. **Processing**: Categorize → Rank → Filter
4. **Assembly**: Format → Template → Render
5. **Delivery**: Validate → HTTP POST → Confirm

### 5.3 External Dependencies

| Library | Purpose | Version |
|---------|---------|---------|
| feedparser | RSS feed parsing | Latest |
| requests | HTTP requests | Latest |
| beautifulsoup4 | HTML scraping | Latest |
| yt-dlp | YouTube video fetching | Latest |
| youtube-transcript-api | Video transcript extraction | Latest |

---

## 6. Configuration

### 6.1 Sources Configuration (`config/sources.yaml`)

```yaml
newsletters:
  - name: "Superhuman AI"
    url: "https://superhuman.ai/newsletter"
  - name: "The Rundown AI"
    url: "https://www.therundown.ai"
  - name: "DeepLearning.AI The Batch"
    url: "https://www.deeplearning.ai/the-batch"

youtube_channels:
  - name: "Lev Selector"
    channel_id: "UCA4GfsgbI09cLzonTKryC6g"
  - name: "IndyDevDan"
    channel_id: "UC_x36zCEGilGpB1m-V4gmjg"
```

### 6.2 Settings Configuration (`config/settings.yaml`)

```yaml
schedule:
  delivery_day: 0  # 0=Monday, 1=Tuesday, ..., 6=Sunday
  delivery_time: "09:00"  # 24-hour format

content:
  window_days: 7  # Look back 7 days for content
  min_items_per_category: 1  # Minimum articles per category

ai:
  filter_threshold: 0.7  # Relevance threshold (0.0-1.0)
  max_categories: 4  # Maximum number of topic categories
```

### 6.3 Environment Variables (`.env`)

```
TELEGRAM_BOT_TOKEN=<your_bot_token>
TELEGRAM_CHAT_ID=<your_chat_id>
AI_SERVICE_TYPE=ollama
AI_MODEL_PATH=llama2
DATABASE_PATH=data/newsletter.db
LOG_DIR=logs
DELIVERY_DAY=0
CONTENT_WINDOW_DAYS=7
```

---

## 7. User Stories

### 7.1 Daily Newsletter Reception
**As a** user interested in AI news
**I want** to receive a daily newsletter with curated AI content
**So that** I stay updated without manually checking multiple sources

**Acceptance Criteria**:
- ✅ Newsletter delivers every day at configured time
- ✅ Contains articles from all configured sources
- ✅ Includes YouTube video summaries
- ✅ Messages arrive via Telegram within seconds

### 7.2 Content Quality
**As a** newsletter subscriber
**I want** to see only real articles, not error pages or blocked messages
**So that** the newsletter is useful and relevant

**Acceptance Criteria**:
- ✅ Blocked pages are filtered out
- ✅ Error messages don't appear in headlines
- ✅ YouTube summaries come from actual transcripts
- ✅ Duplicate articles are removed

### 7.3 Easy Configuration
**As a** system administrator
**I want** to easily add or remove content sources
**So that** I can customize the newsletter to my needs

**Acceptance Criteria**:
- ✅ Sources configured in simple YAML file
- ✅ No code changes required to add sources
- ✅ Changes take effect immediately
- ✅ Configuration is documented

### 7.4 Automatic Scheduling
**As a** a user
**I want** the newsletter to run automatically without manual intervention
**So that** I receive it reliably every day

**Acceptance Criteria**:
- ✅ Windows Task Scheduler integration
- ✅ Configurable schedule (daily, weekly, etc.)
- ✅ Automatic restart on system reboot
- ✅ Detailed logging for troubleshooting

---

## 8. Success Metrics

### 8.1 Functional Metrics
- **Content Collection Rate**: 100% success rate for available sources
- **Deduplication Accuracy**: No duplicate articles in final newsletter
- **Error Page Filtering**: 100% removal of blocked/error pages
- **Delivery Success Rate**: 99%+ messages delivered to Telegram

### 8.2 Performance Metrics
- **Pipeline Execution Time**: < 2 minutes
- **Content Freshness**: < 1 hour from source to delivery
- **Uptime**: > 99% scheduled runs completed successfully

### 8.3 Quality Metrics
- **Article Relevance**: High-quality AI content only
- **Summary Accuracy**: Accurate 1-2 line summaries from transcripts
- **Content Diversity**: Balanced representation from all sources

---

## 9. Future Enhancements

### 9.1 Phase 2 Features
- [ ] AI-powered content filtering and relevance scoring
- [ ] Automatic topic categorization
- [ ] Intelligent summarization of articles
- [ ] Multiple language support
- [ ] Web-based dashboard for configuration

### 9.2 Phase 3 Features
- [ ] Email delivery option
- [ ] Slack integration
- [ ] Content rating system
- [ ] User preferences (topics, sources)
- [ ] Analytics and engagement tracking

### 9.3 Phase 4 Features
- [ ] Mobile app for iOS/Android
- [ ] Content curation by community votes
- [ ] Personalized recommendations
- [ ] Multi-user accounts and subscriptions

---

## 10. Risk Assessment

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Source unavailability | Low | Medium | Graceful error handling, continue with other sources |
| YouTube API rate limits | Medium | Low | Implement rate limiting and retry logic |
| Telegram API issues | Medium | Low | Direct HTTP fallback, detailed error logging |
| Blocked requests | Medium | Medium | User-Agent headers, request throttling |
| Database corruption | High | Very Low | Regular backups, SQLite reliability |
| Scheduling failures | High | Low | Task Scheduler native reliability, system logs |

---

## 11. Success Criteria

✅ **MVP Requirements** (Current Release)
- Automated collection from 3 newsletters and 2 YouTube channels
- Deduplication of identical articles
- Newsletter formatting with headlines and links
- YouTube video transcripts with 1-2 line summaries
- Daily delivery via Telegram
- Windows Task Scheduler integration
- Comprehensive logging and error handling

✅ **Quality Requirements**
- No blocked or error pages in output
- No duplicate articles
- Accurate YouTube summaries from transcripts
- Clean, readable message format
- All 15+ articles successfully delivered

---

## 12. Appendix

### 12.1 Glossary
- **RSS Feed**: Really Simple Syndication format for content distribution
- **Transcript**: Text extracted from video audio/captions
- **Deduplication**: Process of removing duplicate items
- **Telegram Bot**: Automated agent for sending messages via Telegram
- **Task Scheduler**: Windows built-in tool for scheduling tasks

### 12.2 References
- Telegram Bot API: https://core.telegram.org/bots/api
- Feedparser Documentation: https://feedparser.readthedocs.io/
- yt-dlp Documentation: https://github.com/yt-dlp/yt-dlp
- YouTube Transcript API: https://github.com/jdepoix/youtube-transcript-api

### 12.3 Document History
| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-11-24 | AI Newsletter Team | Initial PRD |

---

**Document Status**: APPROVED FOR PRODUCTION
**Last Review Date**: 2025-11-24
**Next Review Date**: 2025-12-24
