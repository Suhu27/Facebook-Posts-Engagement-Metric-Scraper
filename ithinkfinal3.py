import requests
import json
import re
import time
import random
import os
import csv
import sys
import signal
from http.cookiejar import MozillaCookieJar
from datetime import datetime, timezone

# ==============================================================================
# 🔧 CONFIGURATION
# ==============================================================================

# CHANGE THIS FOR EACH ACCOUNT
TARGET_ACCOUNT = 'ysrcpofficial'
TARGET_ID = '100050584325297' 

COOKIE_FILE = 'facebook_cookies.txt'
CURSOR_FILE = f"{TARGET_ACCOUNT}_facebook_cursor.json"

# CORRECT DOC IDS
FILTERED_DOC_ID = '25560331103655089'  # For Date Filtering
VIDEO_DOC_ID    = '25334326422853755'  # For Metrics
COMMENT_DOC_ID  = '25515916584706508'  # For Comments

# Limits
MAX_PAGES_PER_SESSION = 2000
MAX_COMMENTS_PER_POST = 40
API_SAFETY_LIMIT = 5000 

TIMELINES = [
    {
        "name": "Timeline 3 (Jan-May 2024)",
        "start": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "end": datetime(2024, 5, 11, 23, 59, 59, tzinfo=timezone.utc),
        "output": f"{TARGET_ACCOUNT}_JanMay2024.csv"
    },
    {
        "name": "Timeline 2 (Oct-Dec 2023)",
        "start": datetime(2023, 10, 1, tzinfo=timezone.utc),
        "end": datetime(2023, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
        "output": f"{TARGET_ACCOUNT}_OctDec2023.csv"
    },
    {
        "name": "Timeline 1 (Jun-Sep 2023)",
        "start": datetime(2023, 6, 1, tzinfo=timezone.utc),
        "end": datetime(2023, 9, 30, 23, 59, 59, tzinfo=timezone.utc),
        "output": f"{TARGET_ACCOUNT}_JunSep2023.csv"
    }
]

class FacebookScraper:
    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            'authority': 'www.facebook.com',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://www.facebook.com',
            'referer': f'https://www.facebook.com/{TARGET_ACCOUNT}',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'sec-fetch-site': 'same-origin',
        }
        self.context = {}
        self.stats = {'posts': 0, 'views_fixed': 0, 'api_calls': 0, 'start_time': time.time()}
        self.processed_ids = set()
        
        # State for Signal Handler
        self.current_cursor = None
        self.current_idx = 0
        self.current_before_time = None
        
        signal.signal(signal.SIGINT, self.signal_handler)

    def signal_handler(self, sig, frame):
        print(f"\n\n CTRL+C DETECTED! Saving Checkpoint...")
        self.save_checkpoint(self.current_cursor, self.current_idx, self.current_before_time)
        print(" Checkpoint Saved. Exiting safely.")
        sys.exit(0)

    def validate_session(self):
        try:
            r = self.session.get('https://www.facebook.com/api/graphql/', headers=self.headers, allow_redirects=False)
            if r.status_code == 302 or 'login' in r.headers.get('Location', ''): return False
            return True
        except: return False

    def load_cookies(self):
        if not os.path.exists(COOKIE_FILE):
            print(f" FATAL: {COOKIE_FILE} not found."); sys.exit(1)
        try:
            cj = MozillaCookieJar(COOKIE_FILE)
            cj.load(ignore_discard=True, ignore_expires=True)
            self.session.cookies = cj
            print(" Cookies loaded.")
        except Exception as e:
            print(f" Cookie Error: {e}"); sys.exit(1)

    def get_cookie(self, name):
        for c in self.session.cookies:
            if c.name == name: return c.value
        return None

    def handshake(self):
        print(" Authenticating...")
        try:
            resp = self.session.get(f'https://www.facebook.com/{TARGET_ACCOUNT}', headers=self.headers, timeout=30)
            html = resp.text
            dtsg = re.search(r'"DTSGInitialData",\[\],\{"token":"([^"]+)"', html)
            lsd = re.search(r'"LSD",\[\],\{"token":"([^"]+)"', html)
            rev = re.search(r'"client_revision":(\d+),', html)
            
            if not dtsg or not lsd:
                print("❌ Auth tokens not found. Check cookies."); return False
            
            self.context = {
                'fb_dtsg': dtsg.group(1),
                'lsd': lsd.group(1),
                '__rev': rev.group(1) if rev else '1000000000',
                '__user': self.get_cookie('c_user'),
            }
            print(f" Authenticated (User: {self.context['__user']})")
            return True
        except Exception as e:
            print(f"❌ Handshake Error: {e}"); return False

    def graphql_request(self, doc_id, variables):
        payload = {
            'av': self.context['__user'],
            '__user': self.context['__user'],
            '__a': '1',
            'fb_dtsg': self.context['fb_dtsg'],
            'lsd': self.context['lsd'],
            '__rev': self.context['__rev'],
            'fb_api_caller_class': 'RelayModern',
            'doc_id': doc_id,
            'variables': json.dumps(variables),
        }
        try:
            self.stats['api_calls'] += 1
            resp = self.session.post('https://www.facebook.com/api/graphql/', headers=self.headers, data=payload, timeout=30)
            if resp.status_code != 200: return None
            return [json.loads(line) for line in resp.text.split('\n') if line.strip()]
        except: return None

    # --- VIEW COUNT LOGIC ---
    def extract_views_from_data(self, data):
        views = 0
        def search(obj, depth=0):
            nonlocal views
            if depth > 25: return
            if isinstance(obj, dict):
                if 'play_count' in obj:
                     val = obj['play_count']
                     if isinstance(val, int): views = max(views, val)
                for k in ['video_view_count', 'view_count']:
                    if k in obj:
                        val = obj[k]
                        if isinstance(val, int): views = max(views, val)
                        elif isinstance(val, dict): views = max(views, val.get('count', 0))
                for v in obj.values(): search(v, depth+1)
            elif isinstance(obj, list):
                for i in obj: search(i, depth+1)
        search(data)
        return views

    def fetch_video_metrics_html_fallback(self, video_id):
        time.sleep(random.uniform(5, 10)) 
        urls = [f"https://www.facebook.com/watch/?v={video_id}", f"https://www.facebook.com/reel/{video_id}"]
        for url in urls:
            try:
                resp = self.session.get(url, headers=self.headers, timeout=15)
                html = resp.text
                m1 = re.search(r'"play_count":\s*"?(\d+)"?', html)
                if m1: return int(m1.group(1))
                m2 = re.search(r'"video_view_count":\s*"?(\d+)"?', html)
                if m2: return int(m2.group(1))
                m3 = re.search(r'"interactionCount":"(\d+)"', html)
                if m3: return int(m3.group(1))
            except: pass
        return 0

    def get_metrics_strategy(self, story, video_id):
        views = self.extract_views_from_data(story)
        if views > 0: return views

        variables = {
            "count": 5, "cursor": None, "scale": 1, "should_use_stream": True,
            "video_feed_context_data": {
                "request_type": "NORMAL", "seed_video_id": video_id,
                "surface_type": "FEED_VIDEO_DEEP_DIVE", "video_channel_entry_point": "NEWSFEED"
            }
        }
        data = self.graphql_request(VIDEO_DOC_ID, variables)
        if data:
            views = self.extract_views_from_data(data)
            if views > 0: return views

        views = self.fetch_video_metrics_html_fallback(video_id)
        if views > 0:
            self.stats['views_fixed'] += 1
            return views
        return 0

    # --- HELPERS ---
    def fetch_comments(self, feedback_id):
        if not feedback_id: return []
        all_comments = []
        cursor = None
        for _ in range(5):
            if len(all_comments) >= MAX_COMMENTS_PER_POST: break
            variables = {
                "commentsAfterCount": 20, "commentsAfterCursor": cursor, "feedLocation": "TIMELINE",
                "focusCommentID": None, "scale": 1, "useDefaultActor": False, "id": feedback_id,
            }
            data = self.graphql_request(COMMENT_DOC_ID, variables)
            if not data: break
            
            page_comments = []
            next_cursor = None
            
            def extract(obj, depth=0):
                nonlocal next_cursor
                if depth > 25: return
                if isinstance(obj, dict):
                    if 'end_cursor' in obj: next_cursor = obj.get('end_cursor')
                    if 'body' in obj and isinstance(obj['body'], dict):
                        text = obj['body'].get('text', '').strip()
                        if text:
                            clean = text.replace('\n', ' ').replace('\r', ' ')
                            author = obj.get('author', {}).get('name', 'Unknown') if isinstance(obj.get('author'), dict) else "Unknown"
                            page_comments.append({"user": author, "text": clean})
                    for v in obj.values(): extract(v, depth+1)
                elif isinstance(obj, list):
                    for i in obj: extract(i, depth+1)
            extract(data)
            for c in page_comments:
                if not any(x['text'] == c['text'] for x in all_comments): all_comments.append(c)
            if not next_cursor: break
            cursor = next_cursor
            time.sleep(0.5)
        return all_comments[:MAX_COMMENTS_PER_POST]

    def extract_metrics(self, story):
        likes = 0; shares = 0; comments = 0
        def search(obj, depth=0):
            nonlocal likes, shares, comments
            if depth > 15: return
            if isinstance(obj, dict):
                if 'reaction_count' in obj:
                    val = obj['reaction_count']
                    if isinstance(val, dict): likes = max(likes, val.get('count', 0))
                    elif isinstance(val, int): likes = max(likes, val)
                if 'share_count' in obj:
                    val = obj['share_count']
                    if isinstance(val, dict): shares = max(shares, val.get('count', 0))
                    elif isinstance(val, int): shares = max(shares, val)
                if 'comment_rendering_instance' in obj:
                    cri = obj['comment_rendering_instance']
                    if isinstance(cri, dict):
                        val = cri.get('comments', {})
                        if isinstance(val, dict): comments = max(comments, val.get('total_count', 0))
                        elif isinstance(val, int): comments = max(comments, val)
                for v in obj.values(): search(v, depth+1)
            elif isinstance(obj, list):
                for i in obj: search(i, depth+1)
        search(story)
        return likes, shares, comments

    def determine_post_type(self, story):
        post_type = "Photo"
        def scan(obj, depth=0):
            nonlocal post_type
            if depth > 15: return
            if isinstance(obj, dict):
                if 'media' in obj:
                    m = obj['media']
                    if isinstance(m, dict):
                        t = str(m.get('__typename', '')).lower()
                        if 'video' in t: post_type = 'Video'
                        if 'reel' in t: post_type = 'Reel'
                if 'clips_metadata' in obj and obj.get('clips_metadata'): post_type = 'Reel'
                for v in obj.values(): scan(v, depth+1)
            elif isinstance(obj, list):
                for i in obj: scan(i, depth+1)
        scan(story)
        return post_type

    def get_video_id(self, story, post_id):
        vid_id = None
        def search(obj, depth=0):
            nonlocal vid_id
            if vid_id or depth > 15: return
            if isinstance(obj, dict):
                if 'video' in obj and isinstance(obj['video'], dict) and 'id' in obj['video']:
                    vid_id = obj['video']['id']
                for v in obj.values(): search(v, depth+1)
            elif isinstance(obj, list):
                for i in obj: search(i, depth+1)
        search(story)
        return vid_id if vid_id else post_id

    #  PROCESS TIMELINE (Raw Story Support)
    def process_timeline(self, json_data):
        posts = []
        cursor = None
        for item in json_data:
            if 'data' not in item: continue
            try:
                node = item['data'].get('node', {})
                timeline = node.get('timeline_list_feed_units') or node.get('timeline_feed_units') or node.get('profile_timeline_feed_units')
                is_direct_story = 'post_id' in node
                
                if not timeline and not is_direct_story: continue

                if timeline and 'page_info' in timeline:
                    cursor = timeline['page_info'].get('end_cursor')
                
                edges = timeline.get('edges', []) if timeline else [{'node': node}]

                for edge in edges:
                    story = edge.get('node', {})
                    if not story: continue
                    post_id = story.get('post_id')
                    
                    ts = None
                    def get_ts(o):
                        nonlocal ts
                        if isinstance(o, dict):
                            if 'creation_time' in o: ts = o['creation_time']
                            else:
                                for v in o.values(): get_ts(v)
                    get_ts(story)
                    
                    fbid = None
                    def get_fb(o):
                        nonlocal fbid
                        if isinstance(o, dict):
                            if 'feedback' in o:
                                fb = o['feedback']
                                if isinstance(fb, dict) and 'id' in fb: fbid = fb['id']
                            else:
                                for v in o.values(): get_fb(v)
                    get_fb(story)
                    caption = ""
                    try: caption = story['comet_sections']['content']['story']['message']['text']
                    except: pass
                    
                    if post_id and ts:
                        dt = datetime.fromtimestamp(int(ts), timezone.utc)
                        posts.append({'post_id': post_id, 'feedback_id': fbid, 'date_obj': dt, 'caption': caption, 'story_obj': story})
            except: continue
        return posts, cursor

    def save_checkpoint(self, cursor, idx, before_time=None):
        with open(CURSOR_FILE, 'w') as f:
            data = {"cursor": cursor, "timeline_index": idx}
            if before_time: data["before_time"] = before_time
            json.dump(data, f)

    def append_to_csv(self, row, filename):
        exists = os.path.exists(filename)
        with open(filename, 'a', newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, fieldnames=row.keys())
            if not exists: w.writeheader()
            w.writerow(row)

    # --- MAIN RUNNER ---
    def run(self):
        print("="*70)
        print(" FACEBOOK SCRAPER - (HYBRID PAGINATION)")
        print(f" Target: {TARGET_ACCOUNT}")
        print("="*70)

        self.load_cookies()
        if not self.handshake(): return

        start_idx = 0
        start_cursor = None
        start_before_time = None

        if os.path.exists(CURSOR_FILE):
            try:
                with open(CURSOR_FILE, 'r') as f:
                    cp = json.load(f)
                    start_idx = cp.get('timeline_index', 0)
                    start_cursor = cp.get('cursor')
                    start_before_time = cp.get('before_time')
                    print(f" Resuming from Timeline {start_idx}...")
            except: pass

        for idx in range(start_idx, len(TIMELINES)):
            tl = TIMELINES[idx]
            self.current_idx = idx 
            print(f"\n Processing: {tl['name']}")

            if os.path.exists(tl['output']):
                with open(tl['output'], 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    for row in reader: self.processed_ids.add(row['post_id'])

            # Initialize beforeTime
            if idx == start_idx and start_before_time:
                current_before_time = start_before_time
            else:
                current_before_time = int(tl['end'].timestamp())

            variables = {
                "afterTime": int(tl['start'].timestamp()), 
                "beforeTime": current_before_time, 
                "count": 5, 
                "cursor": start_cursor if idx == start_idx else None, 
                "feedLocation": "TIMELINE", "id": TARGET_ID, "postedBy": {"group": "OWNER"},
                "privacy": {"exclusivity": "INCLUSIVE", "filter": "ALL"},
                "renderLocation": "timeline",
                "scale": 1, "stream_count": 1, "feedbackSource": 0, "focusCommentID": None,
                "memorializedSplitTimeFilter": None, "omitPinnedPost": True, "privacySelectorRenderLocation": "COMET_STREAM",
                "taggedInOnly": False, "useDefaultActor": False,
                #  RELAY PARAMS - CRITICAL
                "__relay_internal__pv__GHLShouldChangeAdIdFieldNamerelayprovider": True,
                "__relay_internal__pv__GHLShouldChangeSponsoredDataFieldNamerelayprovider": True,
                "__relay_internal__pv__CometUFICommentAvatarStickerAnimatedImagerelayprovider": False,
                "__relay_internal__pv__IsWorkUserrelayprovider": False,
                "__relay_internal__pv__TestPilotShouldIncludeDemoAdUseCaserelayprovider": False,
                "__relay_internal__pv__FBReels_deprecate_short_form_video_context_gkrelayprovider": True,
                "__relay_internal__pv__FeedDeepDiveTopicPillThreadViewEnabledrelayprovider": False,
                "__relay_internal__pv__FBReels_enable_view_dubbed_audio_type_gkrelayprovider": True,
                "__relay_internal__pv__CometImmersivePhotoCanUserDisable3DMotionrelayprovider": False,
                "__relay_internal__pv__WorkCometIsEmployeeGKProviderrelayprovider": False,
                "__relay_internal__pv__IsMergQAPollsrelayprovider": False,
                "__relay_internal__pv__FBReels_enable_meta_ai_label_gkrelayprovider": True,
                "__relay_internal__pv__FBReelsMediaFooter_comet_enable_reels_ads_gkrelayprovider": True,
                "__relay_internal__pv__FBUnifiedLightweightVideoAttachmentWrapper_wearable_attribution_on_comet_reels_qerelayprovider": False,
                "__relay_internal__pv__CometUFIReactionsEnableShortNamerelayprovider": False,
                "__relay_internal__pv__CometUFIShareActionMigrationrelayprovider": True,
                "__relay_internal__pv__CometUFI_dedicated_comment_routable_dialog_gkrelayprovider": False,
                "__relay_internal__pv__StoriesArmadilloReplyEnabledrelayprovider": True,
                "__relay_internal__pv__FBReelsIFUTileContent_reelsIFUPlayOnHoverrelayprovider": True,
                "__relay_internal__pv__GroupsCometGYSJFeedItemHeightrelayprovider": 206,
                "__relay_internal__pv__ShouldEnableBakedInTextStoriesrelayprovider": True,
                "__relay_internal__pv__StoriesShouldIncludeFbNotesrelayprovider": False
            }
            start_cursor = None 
            page_num = 1
            empty_pages = 0

            while page_num <= MAX_PAGES_PER_SESSION:
                if page_num % 50 == 0:
                    if not self.validate_session():
                        print("\n❌ Session Expired. Saving & Exiting.")
                        self.save_checkpoint(variables['cursor'], idx, variables.get('beforeTime'))
                        sys.exit(1)

                if self.stats['api_calls'] >= API_SAFETY_LIMIT:
                    print(f"\n Safety Limit Reached. Saving & Stopping.")
                    self.save_checkpoint(variables['cursor'], idx, variables.get('beforeTime'))
                    return

                data = None
                for attempt in range(3):
                    data = self.graphql_request(FILTERED_DOC_ID, variables)
                    if data: break
                    if attempt < 2:
                        print(f"⚠️ Network Hiccup. Retrying {attempt+1}/3...")
                        time.sleep(5)
                
                if not data:
                    print("❌ API Error. Saving Checkpoint")
                    self.save_checkpoint(variables['cursor'], idx, variables.get('beforeTime'))
                    break

                posts, next_cursor = self.process_timeline(data)
                
                # ✅ HYBRID PAGINATION (YOUR LOGIC + min())
                if next_cursor:
                    self.current_cursor = next_cursor
                    variables['cursor'] = next_cursor
                    variables['beforeTime'] = None 
                elif posts:
                    # ✅ CORRECT FIX: Use MIN timestamp to avoid duplicates/loops
                    earliest_ts = min(int(p['date_obj'].timestamp()) for p in posts)
                    print(f"   🔄 Hybrid Step: Manual Jump to {datetime.fromtimestamp(earliest_ts, timezone.utc).date()}...")
                    variables['beforeTime'] = earliest_ts - 1
                    variables['cursor'] = None
                    self.current_before_time = earliest_ts - 1
                else:
                    break

                if not posts:
                    print(f"\r   Page {page_num}: No posts...", end="")
                    empty_pages += 1
                    if empty_pages > 3: break
                    time.sleep(2)
                    continue

                empty_pages = 0
                print(f"\n📄 Page {page_num} | Found {len(posts)} posts")

                for p in posts:
                    dt = p['date_obj']
                    if dt < tl['start']: 
                        print(f"   🛑 Reached Start Date ({dt.date()}). Stopping Timeline.")
                        next_cursor = None
                        variables['cursor'] = None
                        posts = [] 
                        break

                    if p['post_id'] in self.processed_ids: continue

                    try:
                        post_type = self.determine_post_type(p['story_obj'])
                        views = 0
                        if post_type in ["Video", "Reel"]:
                            vid_id = self.get_video_id(p['story_obj'], p['post_id'])
                            views = self.get_metrics_strategy(p['story_obj'], vid_id)

                        likes, shares, cmts = self.extract_metrics(p['story_obj'])
                        comments_data = self.fetch_comments(p['feedback_id']) if cmts > 0 else []

                        row = {
                            'post_id': p['post_id'],
                            'date': dt.strftime('%Y-%m-%d %H:%M:%S+00:00'),
                            'type': post_type,
                            'likes': likes, 'comments_count': cmts, 'shares': shares, 'views': views,
                            'caption_raw': p['caption'].replace('\n', ' ').replace('\r', ' '),
                            'comments_json': json.dumps(comments_data, ensure_ascii=False),
                            'url': f"https://www.facebook.com/{p['post_id']}"
                        }
                        self.append_to_csv(row, tl['output'])
                        self.processed_ids.add(p['post_id'])
                        self.stats['posts'] += 1
                        icon = "🎥" if "Video" in post_type or "Reel" in post_type else "📷"
                        print(f"   ✓ {p['date_obj'].date()} | {icon} | V:{views} L:{likes}")

                        time.sleep(random.uniform(3, 7))
                        
                        if self.stats['posts'] > 0 and self.stats['posts'] % 100 == 0:
                            pause = random.uniform(300, 400)
                            print(f"\n☕ Taking a safety break for {int(pause/60)} minutes...")
                            time.sleep(pause)

                    except Exception as e:
                        print(f"   ⚠️ Error: {e}")

                if not next_cursor and not posts: break
                
                self.save_checkpoint(variables.get('cursor'), idx, variables.get('beforeTime'))
                page_num += 1
                time.sleep(random.uniform(2, 5))
            
            print(f"✅ Timeline {tl['name']} Completed.")

if __name__ == "__main__":
    bot = FacebookScraper()
    bot.run()