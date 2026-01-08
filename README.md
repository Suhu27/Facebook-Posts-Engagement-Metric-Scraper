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

#### ⚙️ Configuration: Retrieving GraphQL Doc IDs

Facebook frequently rotates their GraphQL Document IDs. If the scraper returns 400 Bad Request or fails to fetch data, you likely need to update the `doc_id` constants in the main script.

**Prerequisite**
- A modern web browser (Google Chrome, Edge, or Brave).
- An active Facebook session.

**General Extraction Method**
1.  Navigate to the target Facebook profile (e.g., `https://www.facebook.com/tdp.ncbn.official`).
2.  Open **Developer Tools** by pressing `F12` or right-clicking the page and selecting **Inspect**.
3.  Navigate to the **Network** tab.
4.  In the filter search box, type `graphql`.
    *   *Pro Tip: The relevant data queries (Timeline/Feed) usually have the largest payloads, so look for the query with the largest size.*

#### 1. Finding `TIMELINE_DOC_ID` (Filtered Doc ID)
*Used for paginating through the main post feed.*

1.  Clear the Network log (🚫 icon).
2.  Scroll down the profile timeline until a new batch of posts loads.
3.  Look for a POST request with the largest size.
4.  Select the request and view the **Payload** (or Request) tab.
5.  Verify the `fb_api_req_friendly_name` is `ProfileCometTimelineFeedRefetchQuery`.
6.  Copy the numeric string associated with the `doc_id` key.

#### 2. Finding `COMMENT_DOC_ID`
*Used for fetching comments on a specific post.*

1.  Clear the Network log.
2.  Locate any post with comments and click **"View more comments"**.
3.  Select the new network request.
4.  Verify the `fb_api_req_friendly_name` is `CometUFIFeedbackConnectionQuery` (or `CometUFIFetchComments`).
5.  Copy the `doc_id`.

#### 3. Finding `VIDEO_DOC_ID`
*Used for extracting view counts from Reels and Videos.*

1.  Clear the Network log.
2.  Click on any video or Reel to open it in **Theater Mode** (overlay view).
3.  Look for requests with `fb_api_req_friendly_name` matching `CometVideoDeepDiveRootQuery` or `VideoPlayerStreamInfoQuery`.
    *   *Note: There may be multiple video-related requests; look for the one containing `videoID` in the variables.*
4.  Copy the `doc_id`.

**Configuration Update**
Once extracted, update the variables in your script:

```python
# ithinkfinal3.py

FILTERED_DOC_ID = '25560331103655089'  # <--- Paste Timeline ID here
COMMENT_DOC_ID  = '25515916584706508'  # <--- Paste Comment ID here
VIDEO_DOC_ID    = '25334326422853755'  # <--- Paste Video ID here
```

#### ⚙️ User Settings

Adjust these variables at the top of the script:

```python
MAX_COMMENTS_PER_POST = 40    # Stop after X comments per post
API_SAFETY_LIMIT = 5000       # Safety stop after X API calls
MAX_PAGES_PER_SESSION = 2000  # How many "pages" to scroll
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
