import pandas as pd
import sqlite3
import os

os.makedirs("db", exist_ok=True)

datasets = [
    ("data/heart_data.csv", "db/heart_disease.db", "heart_disease"),
    ("data/cancer_data.csv", "db/cancer.db", "cancer"),
    ("data/diabetes_data.csv", "db/diabetes.db", "diabetes"),
]

for csv_path, db_path, table_name in datasets:
    print(f"Loading {csv_path} -> {db_path} table {table_name}")
    df = pd.read_csv(csv_path)
    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]
    conn = sqlite3.connect(db_path)
    df.to_sql(table_name, conn, if_exists="replace", index=False)
    conn.close()
    print(f"Saved {len(df)} rows to {db_path}:{table_name}")