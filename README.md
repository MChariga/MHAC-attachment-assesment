# Manor House attachment assessment: Kobo form, data pipeline and dashboard

```
manor-house-assessment/
├── form/
│   ├── MHAC_Attachment_Assessment_Kobo_Form.xlsx   XLSForm to upload to KoboToolbox
│   ├── build_xlsform.py                            Python that generates the XLSForm (edit questions / class list here)
│   └── mhac_logo.png                               Logo: upload to the Kobo project under Form > Media
├── pipeline/
│   └── kobo_pipeline.py                            Pulls submissions from the latest deployed Kobo form
├── dashboard/
│   ├── index.html                                  Dashboard (HTML + CSS + JavaScript, no build step)
│   └── data/                                       Written by the pipeline: entries.json, entries.js, entries_flat.csv
├── .env.example                                    Template for your Kobo URL, username and password
├── requirements.txt
├── run.sh / run.bat                                One command: fetch data, then open the dashboard
└── README.md
```

Languages: Python 3.9+ (form builder and pipeline), HTML / CSS / JavaScript (dashboard).

## 1. Set up the form in KoboToolbox
1. Upload `form/MHAC_Attachment_Assessment_Kobo_Form.xlsx` as a new project (Projects > New > Upload an XLSForm).
2. In the project open **Form > Media** and upload `form/mhac_logo.png` so the logo shows.
3. **Deploy** the form. After every change, redeploy: the pipeline always reads the latest deployed form.

## 2. Configure the pipeline
```bash
pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env
```
Edit `.env` and fill in the placeholders:

| Setting | Meaning |
|---|---|
| `KOBO_URL` | Your Kobo server, e.g. `https://kf.kobotoolbox.org` or `https://eu.kobotoolbox.org` |
| `KOBO_USERNAME` / `KOBO_PASSWORD` | Your Kobo login (or use `KOBO_API_TOKEN` instead) |
| `KOBO_FORM_NAME` | Part of the form's name. The pipeline picks the **most recently deployed** form that matches |
| `KOBO_ASSET_UID` | Optional. Set it to pin one exact form and skip the name search |
| `KOBO_ONLY_LATEST_VERSION` | `false` = all submissions of the latest deployed form. `true` = only submissions made with the latest version |

Check which form will be used:
```bash
python pipeline/kobo_pipeline.py --list-forms
```
`.env` holds your password: never share it or commit it (it is already in `.gitignore`).

## 3. Run it
```bash
./run.sh          # Windows: run.bat
```
This fetches the data and serves the dashboard at http://localhost:8000. You can also run only
`python pipeline/kobo_pipeline.py` and then open `dashboard/index.html` directly in a browser.

## 4. Automate it
Run the pipeline on a schedule so every new entry reaches the dashboard.

- **Linux / Mac cron** (every 15 minutes):
  `*/15 * * * * cd /path/to/manor-house-assessment && /usr/bin/python3 pipeline/kobo_pipeline.py >> pipeline.log 2>&1`
- **Windows Task Scheduler:** create a task that runs `python pipeline\kobo_pipeline.py` in this folder every 15 minutes.
- **Hosting:** put the `dashboard/` folder on any web server (or serve it with `python3 -m http.server`) and run the
  pipeline on that machine. An open dashboard re-checks `data/entries.json` every minute when served over http.

## How scores work
Each item is marked like a teacher would: Poor (0-2) = 1 mark, Good (3-4) = 2 marks, Very Good (5-6) = 3 marks.
Items ticked "Not applicable" are left out of both the marks scored and the marks possible, so the student is not
penalised. A section or overall result is shown as marks scored out of marks possible (for example 23 / 30) with
the percentage beside it. Levels use the percentage: Poor below 50%, Good 50% to 83.2%, Very Good 83.3% and above
(these are the average of 1.5 and 2.5 marks per item). To change this, edit `PTS`, `BAND_GOOD` and `BAND_VG` near the
top of the script in `dashboard/index.html`.

## Notes
- The dashboard needs an internet connection only for the Google Font; it falls back to system fonts offline.
- The pipeline reads the field names defined in `form/build_xlsform.py` (`reg_no`, `soil_01` ... `watr_04`,
  `challenge_1..10`, `comment_1..10`). If you rename questions, update `SECTIONS` in `pipeline/kobo_pipeline.py` and the
  `sections` list in `dashboard/index.html`.
- To add students, edit the `students` list in `form/build_xlsform.py` and the `ROSTER` list in `dashboard/index.html`, then rebuild and redeploy the form.

## Private public hosting (GitHub Pages with encrypted data)

The published site contains only `data/entries.enc.json` (AES-256-GCM). Viewers type a passphrase and the
data is decrypted in their browser. No names, scores or comments are readable without it.

- The class list is personal data: keep it in `roster.csv` (columns `reg,name`), which is git-ignored.
  `form/build_xlsform.py` and the pipeline read it. On GitHub it lives in the `ROSTER_CSV` secret.
- GitHub secrets needed: `KOBO_URL`, `KOBO_API_TOKEN`, `KOBO_FORM_NAME`, `ROSTER_CSV`, `DASHBOARD_PASSPHRASE`
  (and optionally `KOBO_ASSET_UID`, `KOBO_ONLY_LATEST_VERSION`).
- `DASHBOARD_PASSPHRASE` must be long and random (5+ random words). The encrypted file is public, so a weak
  passphrase can be guessed offline. Change it (secret and everyone you shared it with) if it leaks.
- Local use is unchanged: `run.bat` shows the plaintext dashboard on your own computer only.
