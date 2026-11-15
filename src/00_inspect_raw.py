# Prints what every downloaded raw file contains (layers, column names, first rows) for one
# state, and writes the same text to outputs/raw_inspection_{state}.txt. Called by download_{state}.py.
# Nothing is parsed beyond peeking: text files show their first raw lines, so no delimiter or
# encoding is assumed. Send the output files over so stages 02 to 05 can be written against
# the real column names.

import io
import zipfile

import pandas as pd
import pyogrio

from common import RAW, ROOT

SPATIAL = (".shp", ".gpkg", ".geojson")
TEXT = (".csv", ".txt", ".tab", ".tsv")
pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 40)


def describe_spatial(path):
    info = pyogrio.read_info(path)
    head = pyogrio.read_dataframe(path, max_features=3, read_geometry=False)
    return (f"  features: {info['features']}, crs: {info['crs']}\n"
            f"  fields: {list(info['fields'])}\n{head.to_string()}\n")


def first_lines(handle, n=6):
    # Raw lines exactly as stored; stops early if the file is shorter than n lines
    lines = [handle.readline() for _ in range(n)]
    return "".join(f"  | {line.rstrip()}\n" for line in lines if line)


def run(cfg):
    out = []
    for f in sorted((RAW / cfg["name"]).rglob("*")):
        rel = f.relative_to(RAW)
        suffix = f.suffix.lower()
        if suffix in SPATIAL:
            out.append(f"== {rel}\n{describe_spatial(str(f))}")
        elif suffix in TEXT:
            out.append(f"== {rel}\n{first_lines(open(f, encoding='utf-8', errors='replace'))}")
        elif suffix == ".xlsx":
            # Every sheet's name, size, columns and first rows (needs openpyxl); read as text so
            # codes such as census block IDs keep their leading zeros
            for sheet, df in pd.read_excel(f, sheet_name=None, dtype=str).items():
                out.append(f"== {rel} [sheet: {sheet}]\n  rows: {len(df)}\n  columns: {list(df.columns)}\n"
                           f"{df.head(5).to_string()}\n")
        elif suffix == ".parquet":
            df = pd.read_parquet(f)
            out.append(f"== {rel}\n  rows: {len(df)}\n  columns: {list(df.columns)}\n{df.head(3).to_string()}\n")
        elif suffix == ".zip":
            names = zipfile.ZipFile(f).namelist()
            out.append(f"== {rel}\n  contains: {names}\n")
            if any(n.lower().endswith(".shp") for n in names):
                out.append(describe_spatial(str(f)))
            for n in names:
                if n.lower().endswith(TEXT):
                    raw = zipfile.ZipFile(f).open(n)
                    out.append(f"  -- {n}\n{first_lines(io.TextIOWrapper(raw, encoding='utf-8', errors='replace'))}")
        elif f.is_file():
            out.append(f"== {rel}\n  ({suffix or 'no extension'}, {f.stat().st_size:,} bytes, not inspected)\n")
    text = "\n".join(out)
    print(text)
    dest = ROOT / "outputs" / f"raw_inspection_{cfg['name']}.txt"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text)
    print(f"written to {dest}")