# PrintSight Drive CSV Ingest — n8n setup

Import `printsight-drive-ingest.json` into your n8n instance, then complete the steps below before activating.

## 1. Credentials

**Google Drive (service account)**

- In n8n: Settings → Credentials → New → **Google Service Account API**.
- Upload the JSON key from `n8n/Gdrivekey/printsight-ingest-4bfc0fc48024.json` (paste the contents into the "Service Account Email" / "Private Key" fields, or use the JSON upload option if your n8n version supports it).
- After saving, open each Google Drive node in the workflow and bind this credential (the import does not carry 	credential IDs).
- Nodes that need the credential: `List printer folders`, `List Inbox/Archive/Error`, `List CSVs in Inbox`, `Download CSV`, `Move to Archive`, `Move to Error`, `Write .error.log`.

## 2. Environment variable

Set on the n8n host (so `$env.PRINTSIGHT_INGEST_API_KEY` resolves):

```
PRINTSIGHT_INGEST_API_KEY=<same value as prod backend INGEST_API_KEY>
```

Restart n8n after setting. (Current trial value is `revoria-key-1234567890` — rotate before non-trial use.)

## 3. Replace the root folder ID placeholder

Open `List printer folders` and replace `${ROOT_FOLDER_ID}` in the query string with the literal:

```
1Ta-2DdH8RdXVeZK46ru0Hakdqbq8gGrQ
```

(The placeholder syntax is for readability — n8n does not expand it.)

## 4. How the workflow behaves

```
Schedule (1 min)
  → List printer subfolders of ROOT          (folder name == printer_id)
  → For each printer:
      → List its subfolders → resolve Inbox/Archive/Error IDs by name
      → List non-folder files in Inbox
      → For each file:
          → Skip if createdTime < 60s ago     (let writes settle)
          → Download
          → POST to /api/v1/printers/{printer_id}/uploads/import with X-API-Key
          → On HTTP 200 → move to Archive
          → On non-200  → move to Error + write <name>.error.log alongside
```

Dedup is handled server-side: re-posting the same `(job_id, recorded_at)` returns 200 with `rows_imported:0`, so a re-run of a previously-archived file (if it ever sneaks back into Inbox) is safe — it'll still move to Archive.

## 5. Things to verify in the UI after import

n8n's node JSON schema shifts across versions. After import, click through each node and confirm:

- **List printer folders / List Inbox/Archive/Error / List CSVs in Inbox** — `Resource: File/Folder`, `Operation: Search`, the query string is intact, and "Return All" is on.
- **Download CSV** — `Resource: File, Operation: Download`. Output binary property name defaults to `data` — the HTTP node downstream expects that exact name (`inputDataFieldName: "data"`).
- **POST to import** — Body Content Type is `multipart-form-data`. The `file` parameter must be type **n8n binary** (the dropdown says "Form Binary Data") pointing at `data`. The `source_filename` parameter is a plain text field.
- **HTTP 200?** — left side reads `$json.statusCode` (the HTTP node is configured with `fullResponse: true`, so the body sits under `$json.body`).
- **Move to Archive / Move to Error** — `Resource: File, Operation: Move`. Confirm the `folderId` resolves at runtime.
- **Write .error.log** — `Resource: File, Operation: Upload`. If your n8n version uses different field names for inline text content, switch to "Binary Data: off" and paste the expression into whichever field holds raw text.

## 6. First-run checklist

1. Drop a known-good CSV (e.g. `resourses/sample.csv`) into `<root>/2/Inbox/` via the Drive UI.
2. In n8n, click **Execute Workflow** manually (don't activate yet).
3. Wait ~70s after the drop so the age gate passes, then trigger.
4. Verify:
   - File appears in `<root>/2/Archive/`.
   - Backend logs show a `200` import with `rows_imported > 0` (or `rows_imported: 0` if it's the dedup'd sample).
5. Repeat with a deliberately malformed CSV → expect it in `Error/` plus a `.error.log` sibling.
6. Activate the workflow.

## 7. Known sharp edges

- **Polling overlap**: the schedule fires every 60s; if a previous run is still inside the per-file loop when the next tick fires, you can get concurrent imports for the same printer. Backend handles dedup but will log unique-constraint rollbacks under load (see `drive-csv-ingest` memory). For trial volumes this is fine. Mitigate later by extending the interval or adding a workflow-level lock.
- **No Inbox/Archive/Error**: if a printer folder is missing one of the three subfolders, `Resolve folder IDs` will leave that ID empty and downstream Drive nodes will error. The workflow currently does not pre-validate — add an IF gate if printer onboarding becomes self-service.
- **Large files**: the HTTP node timeout is set to 120s. Backend has its own size limit; if you raise it, raise the n8n timeout to match.
