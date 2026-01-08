# Facebook Page Scraper (Hybrid Pagination)

A specialized research tool for collecting Facebook page data including posts, engagement metrics, and video view counts. Features hybrid pagination for deep timeline scraping and robust session handling.

## 📂 Repository Contents

- `ithinkfinal3.py`: Main scraping script
- `facebook_cookies.txt`: Authentication file (user-generated)

## 🚀 Quick Start

### 1. Installation

```bash
pip install requests
```

### 2. Authentication

1.  Install **"Get cookies.txt LOCALLY"** extension (Chrome/Edge).
2.  Log into `facebook.com`.
3.  Click extension icon > **Export**.
4.  Rename file to `facebook_cookies.txt` and place in script folder.

### 3. Configuration (`ithinkfinal3.py`)

#### Required Identifiers

You must inspect network traffic (F12 > Network) while browsing Facebook to find these IDs.

```python
TARGET_ACCOUNT = 'whitehouse'       # Page username from URL
TARGET_ID = '123456789'             # Numeric Page ID (Found in page source or "About")

# GraphQL Doc IDs (Found in Network tab "graphql" requests body)
FILTERED_DOC_ID = '...'  # Search for "ProfileCometTimelineFeedRefetchQuery"
VIDEO_DOC_ID    = '...'  # Search for video metric queries
COMMENT_DOC_ID  = '...'  # Search for comment pagination queries
```

#### User Preferences

Adjust these variables at the top of the script to match your research needs:

```python
MAX_COMMENTS_PER_POST = 40    # Number of comments to scrape per post
API_SAFETY_LIMIT = 5000       # Max API calls before auto-stop
MAX_PAGES_PER_SESSION = 2000  # Max pages to scroll
```

#### Timelines

Define your data collection periods:

```python
TIMELINES = [
    {
        "name": "Dataset 1",
        "start": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "end": datetime(2024, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
        "output": f"{TARGET_ACCOUNT}_2024.csv"
    },
]
```

### 4. Run Scraper

```bash
python ithinkfinal3.py
```

## 🧠 Core Features

### Hybrid Pagination
Overcomes Facebook's scroll limits by combining:
1.  **Cursor Pagination:** Standard "Next Page" token.
2.  **Time-based Fallback:** Manually jumps backward in time using timestamps when cursors fail, allowing access to older data.

### Video Metrics
Uses a 3-step fallback strategy (Feed Data → Deep Dive API → HTML Scraping) to ensure accurate video view counts.

## 📊 CSV Output

| Column | Description |
| :--- | :--- |
| `post_id` | Unique post identifier |
| `date` | Publication timestamp (UTC) |
| `type` | Photo, Video, or Reel |
| `likes` | Reaction count |
| `comments_count` | Total comment count |
| `shares` | Share count |
| `views` | View count (videos only) |
| `caption_raw` | Post text content |
| `comments_json` | JSON list of comments |
| `url` | Direct post link |

## ⚠️ Safety Features

- **Checkpointing:** Saves progress to `_facebook_cursor.json`. Restarting the script resumes exactly where it left off.
- **Rate Limiting:** Auto-pauses (5 mins) after every 100 posts.
- **Session Checks:** Validates cookies before major batch operations.

## License

MIT License
