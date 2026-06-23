import sqlite3
import json
import argparse
from pathlib import Path
from collections import defaultdict

def export_feed_logs(db_path: str, output_path: str):
    """
    Exports a reconstructed timeline of content for each user
    based on the current follower graph and photo timestamps.
    """
    print(f"Exporting feed logs from {db_path}...")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get follower graph
    following_map = defaultdict(list)
    for row in cursor.execute("SELECT follower_id, user_id FROM follow WHERE action='follow'"):
        following_map[row['follower_id']].append(row['user_id'])
        
    # Get all active photos
    photos = []
    for row in cursor.execute("SELECT id, user_id, caption, created_at, viral_score FROM photos WHERE is_removed=0 ORDER BY created_at ASC"):
        photos.append(dict(row))
        
    out_file = Path(output_path) / "feed_logs.jsonl"
    with open(out_file, "w") as f:
        # Reconstruct what each user's feed looks like
        for user_id, following in following_map.items():
            user_feed = [p for p in photos if p['user_id'] in following]
            # sort by created_at desc to simulate a home feed
            user_feed.sort(key=lambda x: x['created_at'], reverse=True)
            
            feed_data = {
                "user_id": user_id,
                "home_feed_length": len(user_feed),
                "feed": user_feed
            }
            f.write(json.dumps(feed_data) + "\n")
            
    conn.close()
    print(f"Exported feed logs to {out_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="example/yphotosharing.db")
    parser.add_argument("--out", default="example/exports/")
    args = parser.parse_args()
    
    Path(args.out).mkdir(parents=True, exist_ok=True)
    export_feed_logs(args.db, args.out)
