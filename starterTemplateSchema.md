analytics-template/
│
├── CLAUDE.md                  ← Always-on instructions
│
├── data/
│   ├── raw/                   ← Source files; never modified
│   └── processed/             ← Claude Code writes here
│
├── src/
│   ├── ingest.py              ← Load data (SAS, CSV, Excel)
│   ├── clean.py               ← QA and validation
│   ├── analyze.py             ← Stats / modeling
│   └── report.py             ← Output generation
│
├── notebooks/                 ← Exploratory work only
├── tests/                     ← Pytest; uses synthetic data
├── reports/                   ← Figures, tables, documents
│
├── todo.txt                   ← Created fresh each session
├── requirements.txt
└── .env                       ← Paths, credentials (gitignored)