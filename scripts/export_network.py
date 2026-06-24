import sqlite3
import csv
import argparse
from pathlib import Path

def export_network(db_path: str, output_path: str):
    print(f"Exporting network from {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Export node list
    nodes_query = "SELECT id, is_shadow_banned, stress_level FROM user_mgmt"
    nodes_file = Path(output_path) / "nodes.csv"
    with open(nodes_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "is_shadow_banned", "stress_level"])
        for row in cursor.execute(nodes_query):
            writer.writerow(row)
            
    # Export edge list (follow graph)
    edges_query = "SELECT follower_id, user_id, action FROM follow WHERE action='follow'"
    edges_file = Path(output_path) / "edges.csv"
    with open(edges_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["source", "target", "action"])
        for row in cursor.execute(edges_query):
            writer.writerow(row)
            
    conn.close()
    print(f"Exported nodes to {nodes_file} and edges to {edges_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="example/yphotosharing.db")
    parser.add_argument("--out", default="example/exports/")
    args = parser.parse_args()
    
    Path(args.out).mkdir(parents=True, exist_ok=True)
    export_network(args.db, args.out)
