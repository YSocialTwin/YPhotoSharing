import sqlite3
import json
import argparse
from pathlib import Path
from collections import defaultdict

def export_content_cascade(db_path: str, output_path: str):
    """
    Exports share cascades (virality trees) by tracing parent_photo_id links.
    """
    print(f"Exporting content cascades from {db_path}...")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all photos
    photos = {}
    cascades = defaultdict(list)
    
    for row in cursor.execute("SELECT id, user_id, parent_photo_id, created_at, viral_score FROM photos"):
        photos[row['id']] = dict(row)
        
    for photo_id, photo in photos.items():
        parent_id = photo['parent_photo_id']
        if parent_id:
            cascades[parent_id].append({
                "share_id": photo_id,
                "user_id": photo['user_id'],
                "created_at": photo['created_at'],
                "viral_score": photo['viral_score']
            })
            
    # Filter only those that have cascades
    active_cascades = {k: v for k, v in cascades.items() if len(v) > 0}
    
    out_file = Path(output_path) / "content_cascades.json"
    with open(out_file, "w") as f:
        json.dump(active_cascades, f, indent=2)
            
    conn.close()
    print(f"Exported content cascades to {out_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="example/yphotosharing.db")
    parser.add_argument("--out", default="example/exports/")
    args = parser.parse_args()
    
    Path(args.out).mkdir(parents=True, exist_ok=True)
    export_content_cascade(args.db, args.out)
